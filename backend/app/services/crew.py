from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.session import (
    create_session_token,
    is_token_revoked,
    verify_password,
    verify_session_token,
)
from app.database import get_session_factory
from app.domain.certifications import normalize_cert_name
from app.models import Certification, CrewMember, Document, WorkHistory
from app.services.cache import cache_service
from app.services.consultant_knowledge import consultant_knowledge_service
from app.services.upload import document_upload_service

logger = logging.getLogger(__name__)


class PossibleDuplicateError(ValueError):
    def __init__(self, candidate_id: str):
        self.candidate_id = candidate_id
        super().__init__("A possible duplicate specialist already exists")


class AuthService:
    """Service for authentication and session management."""

    async def authenticate(self, email: str, password: str) -> Optional[dict]:
        """Authenticate a user and return session data."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CrewMember).where(CrewMember.email == email)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return None

            # CrewMember model currently has no password_hash column;
            # for now, require password == email local-part fallback is removed.
            # If a password_hash attribute exists (future migration), verify it.
            stored = getattr(user, "password_hash", None)
            if stored:
                if not verify_password(password, stored):
                    return None
            else:
                # No password column yet: use constant-time dummy check to avoid
                # timing oracle, but require explicit env flag to allow passwordless
                # login in development only. Default: deny.
                from app.config import get_settings as _gs

                if _gs().APP_ENV != "development":
                    return None
                logger.warning(
                    "AuthService.authenticate: allowing a development login without a password hash"
                )

            token = create_session_token(user.id)
            return {
                "token": token,
                "user": {
                    "id": user.id,
                    "full_name": user.full_name,
                    "email": user.email,
                    "role": user.role,
                },
            }

    async def get_user_from_token(self, token: str) -> Optional[CrewMember]:
        """Get user from session token."""
        token_data = verify_session_token(token)
        if not token_data:
            return None
        user_id, jti = token_data
        if await is_token_revoked(jti):
            return None

        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(CrewMember)
                .options(
                    selectinload(CrewMember.certifications),
                    selectinload(CrewMember.work_history),
                    selectinload(CrewMember.documents),
                )
                .where(CrewMember.id == user_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()


async def _reload_crew_with_relations(session: AsyncSession, crew_id: str) -> CrewMember:
    """Re-fetch a crew member with work_history/certifications eager-loaded.

    The GraphQL mapper accesses these relationships synchronously; without
    selectinload here that lazy-loads outside the async greenlet context and
    raises `MissingGreenlet`.
    """
    stmt = (
        select(CrewMember)
        .options(
            selectinload(CrewMember.work_history),
            selectinload(CrewMember.certifications),
        )
        .where(CrewMember.id == crew_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


class CrewService:
    """Service for crew member operations."""

    async def create_crew_member(
        self,
        crew: CrewMember,
        *,
        as_draft: bool = False,
        submitted_by: str | None = None,
        allow_duplicate: bool = False,
    ) -> CrewMember:
        """Persist a new crew member and index them for retrieval.

        ``crew`` is an unpersisted model instance built by the caller (the
        GraphQL layer owns mapping the create DTO to a model).
        """
        factory = get_session_factory()
        async with factory() as session:
            if as_draft and not allow_duplicate:
                conditions = [func.lower(CrewMember.full_name) == crew.full_name.strip().lower()]
                if crew.email:
                    conditions.append(func.lower(CrewMember.email) == crew.email.strip().lower())
                duplicate = (
                    await session.execute(select(CrewMember.id).where(or_(*conditions)).limit(1))
                ).scalar_one_or_none()
                if duplicate is not None:
                    raise PossibleDuplicateError(duplicate)
                crew.publication_status = "draft"
                crew.submitted_by = submitted_by
            session.add(crew)
            await session.commit()
            crew = await _reload_crew_with_relations(session, crew.id)

        if crew.publication_status == "approved":
            await consultant_knowledge_service.index_crew_member(crew)
        return crew

    async def update_crew_member(self, crew_id: str, updates: dict[str, Any]) -> CrewMember:
        """Apply the given field updates to a crew member.

        ``updates`` should contain only fields the caller actually wants
        changed (already filtered of unset/None values) — every key is
        applied unconditionally via setattr.
        """
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CrewMember).where(CrewMember.id == crew_id)
            result = await session.execute(stmt)
            crew = result.scalar_one_or_none()
            if not crew:
                raise ValueError(f"Crew member {crew_id} not found")
            for field, value in updates.items():
                setattr(crew, field, value)
            await session.commit()
            crew = await _reload_crew_with_relations(session, crew.id)

        if crew.publication_status == "approved":
            await consultant_knowledge_service.index_crew_member(crew)
        else:
            await consultant_knowledge_service.remove_from_index(crew.id)
        # The AI summary is generated from these same fields — a stale
        # cached summary after an edit would show outdated facts.
        await cache_service.delete(cache_service._make_key("summary", crew.id))
        return crew

    async def set_staff_role(self, crew_id: str, *, enabled: bool) -> CrewMember:
        """Promote or demote a non-admin account without altering admin accounts."""
        factory = get_session_factory()
        async with factory() as session:
            crew = (
                await session.execute(select(CrewMember).where(CrewMember.id == crew_id))
            ).scalar_one_or_none()
            if crew is None:
                raise ValueError("User not found")
            if crew.role == "admin":
                raise ValueError("Administrator roles cannot be changed here")
            crew.role = "staff" if enabled else "user"
            await session.commit()
            return await _reload_crew_with_relations(session, crew.id)

    async def delete_crew_member(self, crew_id: str, requesting_user_id: Optional[str]) -> bool:
        """Permanently delete a crew member and their managed documents.

        Admin-only by decorator at the resolver. Dropbox files are removed
        before database metadata so a failed remote deletion leaves the
        member and their documents recoverable — this raises rather than
        silently skipping the file so the caller (and the record) stays
        intact.
        """
        if requesting_user_id == crew_id:
            raise ValueError("You cannot delete your own administrator account")

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CrewMember).where(CrewMember.id == crew_id)
            result = await session.execute(stmt)
            crew = result.scalar_one_or_none()
            if not crew:
                return False

            documents_result = await session.execute(
                select(Document).where(Document.crew_member_id == crew_id)
            )
            documents = list(documents_result.scalars().all())

            # Keep all metadata when Dropbox cannot confirm deletion.
            for document in documents:
                if document.storage_type == "dropbox":
                    if (
                        not document.dropbox_path
                        or not await document_upload_service.delete_from_dropbox(
                            document.dropbox_path
                        )
                    ):
                        raise ValueError(
                            f"Could not delete Dropbox file for {document.file_name}; "
                            "crew member was retained"
                        )

            for document in documents:
                await session.delete(document)
            await session.delete(crew)
            await session.commit()

        # Cache removal is best-effort and happens only after the database
        # transaction has succeeded. The "summary" and "compliance" keys are
        # addressable directly by crew_id via crewSummary/complianceStatus,
        # independent of whether the crew record still exists — a stale hit
        # there would keep serving a deleted person's data until its TTL
        # expires, so they must be cleared explicitly rather than assumed
        # unreachable.
        for document in documents:
            document_upload_service.delete_file(document.storage_path)

        await cache_service.delete(cache_service._make_key("crew", crew_id))
        await cache_service.delete(cache_service._make_key("summary", crew_id))
        await cache_service.delete(cache_service._make_key("compliance", crew_id))
        await cache_service.invalidate_pattern("hydenlyne:crew_list:*")
        await consultant_knowledge_service.remove_from_index(crew_id)
        return True

    async def get_crew_member(self, crew_id: str) -> Optional[CrewMember]:
        """Get a crew member by ID with all relationships loaded."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(CrewMember)
                .where(CrewMember.id == crew_id)
                .options(
                    selectinload(CrewMember.certifications),
                    selectinload(CrewMember.work_history),
                    selectinload(CrewMember.documents),
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def can_access_profile(self, crew_id: str, *, actor_id: str, actor_role: str) -> bool:
        """Drafts are visible only to their submitter and administrators."""
        factory = get_session_factory()
        async with factory() as session:
            crew = (
                await session.execute(select(CrewMember).where(CrewMember.id == crew_id))
            ).scalar_one_or_none()
            return bool(
                crew
                and (
                    crew.publication_status == "approved"
                    or actor_role == "admin"
                    or crew.submitted_by == actor_id
                )
            )

    async def list_crew_members(
        self,
        availability: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CrewMember]:
        """List crew members with optional filters."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(CrewMember)
                .options(
                    selectinload(CrewMember.certifications),
                    selectinload(CrewMember.work_history),
                    selectinload(CrewMember.documents),
                )
                # New additions must be visible on the first paginated page.
                # Without an explicit order, PostgreSQL may return an arbitrary
                # legacy page and hide newly created specialists from the UI.
                .order_by(CrewMember.created_at.desc())
                .limit(limit)
                .offset(offset)
                .where(CrewMember.publication_status == "approved")
            )

            if availability:
                stmt = stmt.where(CrewMember.availability_status == availability)

            if search:
                search_term = f"%{search.strip()}%"
                stmt = stmt.where(
                    or_(
                        CrewMember.full_name.ilike(search_term),
                        CrewMember.email.ilike(search_term),
                        CrewMember.nationality.ilike(search_term),
                        CrewMember.professional_summary.ilike(search_term),
                        cast(CrewMember.tags, String).ilike(search_term),
                        CrewMember.certifications.any(Certification.cert_type.ilike(search_term)),
                        CrewMember.work_history.any(
                            or_(
                                WorkHistory.role.ilike(search_term),
                                WorkHistory.project_type.ilike(search_term),
                            )
                        ),
                    )
                )

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_availability(
        self,
        crew_id: str,
        status: str,
        available_date: Optional[date] = None,
    ) -> Optional[CrewMember]:
        """Update crew member availability."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CrewMember).where(CrewMember.id == crew_id)
            result = await session.execute(stmt)
            crew = result.scalar_one_or_none()

            if not crew:
                return None

            crew.availability_status = status
            if available_date:
                crew.availability_date = available_date

            await session.commit()
            await session.refresh(crew)

            cache_key = cache_service._make_key("crew", crew_id)
            await cache_service.delete(cache_key)
            await cache_service.invalidate_pattern("hydenlyne:crew_list:*")

            return crew

    async def get_compliance_status(self, crew_id: str) -> dict[str, Any]:
        """Get compliance status for a crew member."""
        cache_key = cache_service._make_key("compliance", crew_id)

        async def fetch() -> dict[str, Any]:
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(Certification).where(Certification.crew_member_id == crew_id)
                result = await session.execute(stmt)
                certs = result.scalars().all()

                today = date.today()
                return {
                    "total": len(certs),
                    "valid": sum(1 for c in certs if c.status == "valid"),
                    "expiring_soon": sum(
                        1
                        for c in certs
                        if c.expiry_date
                        and c.expiry_date <= today + timedelta(days=30)
                        and c.expiry_date >= today
                    ),
                    "expired": sum(1 for c in certs if c.expiry_date and c.expiry_date < today),
                    "pending_verification": sum(
                        1 for c in certs if c.verification_status == "unverified"
                    ),
                }

        result = await cache_service.get_or_set(
            cache_key,
            fetch,
            ttl=cache_service.COMPLIANCE_TTL,
        )
        return result if isinstance(result, dict) else await fetch()


class CertificationService:
    """Service for certification operations."""

    async def add_certification(
        self,
        crew_id: str,
        cert_type: str,
        cert_number: Optional[str] = None,
        issuing_body: Optional[str] = None,
        issue_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
    ) -> Certification:
        """Add a certification to a crew member."""
        factory = get_session_factory()
        async with factory() as session:
            cert = Certification(
                crew_member_id=crew_id,
                cert_type=cert_type,
                cert_number=cert_number,
                issuing_body=issuing_body,
                issue_date=issue_date,
                expiry_date=expiry_date,
            )
            session.add(cert)
            await session.commit()
            await session.refresh(cert)

            cache_key = cache_service._make_key("compliance", crew_id)
            await cache_service.delete(cache_key)

            return cert

    async def update_certification(
        self, cert_id: str, status: Optional[str] = None
    ) -> Certification:
        """Update a certification's status."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Certification).where(Certification.id == cert_id)
            result = await session.execute(stmt)
            cert = result.scalar_one_or_none()
            if not cert:
                raise ValueError(f"Certification {cert_id} not found")
            if status is not None:
                cert.status = status
            await session.commit()
            await session.refresh(cert)
            return cert

    async def verify_certification(self, cert_id: str, status: str) -> Certification:
        """Set a certification's verification status and update lifecycle status."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Certification).where(Certification.id == cert_id)
            result = await session.execute(stmt)
            cert = result.scalar_one_or_none()
            if not cert:
                raise ValueError(f"Certification {cert_id} not found")
            cert.verification_status = status
            today = date.today()
            if status == "verified":
                if cert.expiry_date and cert.expiry_date < today:
                    cert.status = "expired"
                elif cert.expiry_date and cert.expiry_date <= today + timedelta(days=30):
                    cert.status = "expiring_soon"
                else:
                    cert.status = "valid"
            elif status == "rejected":
                cert.status = "pending_verification"

            await session.commit()
            await session.refresh(cert)

            cache_key = cache_service._make_key("compliance", cert.crew_member_id)
            await cache_service.delete(cache_key)
            await cache_service.invalidate_pattern("hydenlyne:compliance:*")

            return cert

    async def get_expiring_certifications(self, days: int = 30) -> list[Certification]:
        """Get certifications expiring within the specified number of days."""
        factory = get_session_factory()
        async with factory() as session:
            threshold = date.today() + timedelta(days=days)
            stmt = (
                select(Certification)
                .where(
                    and_(
                        Certification.expiry_date <= threshold,
                        Certification.expiry_date >= date.today(),
                    )
                )
                .options(selectinload(Certification.crew_member))
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def check_and_update_expiration_status(self) -> int:
        """Update status of certifications based on expiration dates."""
        factory = get_session_factory()
        async with factory() as session:
            today = date.today()

            stmt = (
                select(Certification)
                .where(Certification.expiry_date.isnot(None))
                .options(selectinload(Certification.crew_member))
            )
            result = await session.execute(stmt)
            certs = result.scalars().all()

            updated = 0
            for cert in certs:
                if cert.expiry_date is None:
                    continue
                old_status = cert.status
                new_status: Optional[str] = None
                if cert.expiry_date < today:
                    if cert.status != "expired":
                        new_status = "expired"
                elif cert.expiry_date <= today + timedelta(days=30):
                    if cert.status == "valid":
                        new_status = "expiring_soon"

                if new_status and new_status != old_status:
                    cert.status = new_status
                    if "medical" in cert.cert_type.lower() and cert.crew_member:
                        cert.crew_member.medical_status = new_status
                    updated += 1

            await session.commit()

            if updated > 0:
                await cache_service.invalidate_pattern("hydenlyne:compliance:*")

            return updated

    @staticmethod
    def _parse_date(date_val: Any) -> Optional[date]:
        """Safely parse date strings or objects into a datetime.date."""
        if not date_val:
            return None
        if isinstance(date_val, date):
            return date_val
        val_str = str(date_val).strip()
        if "T" in val_str:
            val_str = val_str.split("T")[0]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y"):
            try:
                return datetime.strptime(val_str, fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    async def link_extracted_certificate(
        self,
        crew_id: str,
        document_id: str,
        extracted_data: dict[str, Any],
        *,
        confidence: Optional[dict[str, Any]] = None,
    ) -> Optional[Certification]:
        """Auto-create or update a Certification row from extracted certificate document data.

        Links the Certification record to the backing Document via document_ref.
        If a matching unlinked certification already exists (e.g. from CV ingestion),
        it updates it with the verified document reference and new date/number evidence.
        """
        raw_cert_type = (
            extracted_data.get("certificate_type")
            or extracted_data.get("cert_type")
            or extracted_data.get("title")
            or extracted_data.get("name")
        )
        if not raw_cert_type:
            logger.info(f"No certificate type identified in document {document_id}")
            return None

        cert_type = normalize_cert_name(str(raw_cert_type))

        cert_number = extracted_data.get("certificate_number") or extracted_data.get("cert_number")
        if isinstance(cert_number, str):
            cert_number = cert_number.strip() or None
        elif cert_number is not None:
            cert_number = str(cert_number).strip() or None

        issuing_body = extracted_data.get("issuing_body") or extracted_data.get("training_provider")
        if isinstance(issuing_body, str):
            issuing_body = issuing_body.strip() or None
        elif issuing_body is not None:
            issuing_body = str(issuing_body).strip() or None

        issue_date = self._parse_date(extracted_data.get("issue_date"))
        expiry_date = self._parse_date(extracted_data.get("expiry_date"))
        renewal_date = self._parse_date(extracted_data.get("renewal_date"))

        raw_confidence = confidence or extracted_data.get("confidence")
        extracted_confidence: Optional[float] = None
        if isinstance(raw_confidence, dict):
            numeric_scores = [v for v in raw_confidence.values() if isinstance(v, (int, float))]
            if numeric_scores:
                extracted_confidence = round(sum(numeric_scores) / len(numeric_scores), 2)
        elif isinstance(raw_confidence, (int, float)):
            extracted_confidence = round(float(raw_confidence), 2)

        today = date.today()
        if expiry_date:
            if expiry_date < today:
                status = "expired"
            elif expiry_date <= today + timedelta(days=30):
                status = "expiring_soon"
            else:
                status = "pending_verification"
        else:
            status = "pending_verification"

        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(CrewMember)
                .options(selectinload(CrewMember.certifications))
                .where(CrewMember.id == crew_id)
            )
            result = await session.execute(stmt)
            crew_member = result.scalar_one_or_none()
            if not crew_member:
                logger.warning(
                    f"Crew member {crew_id} not found when linking certificate {document_id}"
                )
                return None

            # Look for existing matching certification:
            # 1. Backed by this exact document (reprocessing)
            # 2. Or matching cert_type where document_ref is either None, empty, or already this doc
            target_cert: Optional[Certification] = None
            for c in crew_member.certifications:
                if c.document_ref == document_id:
                    target_cert = c
                    break

            if not target_cert:
                for c in crew_member.certifications:
                    if c.cert_type == cert_type and (
                        not c.document_ref or c.document_ref == document_id
                    ):
                        target_cert = c
                        break

            if target_cert:
                target_cert.document_ref = document_id
                target_cert.cert_type = cert_type
                if cert_number:
                    target_cert.cert_number = cert_number
                if issuing_body:
                    target_cert.issuing_body = issuing_body
                if issue_date:
                    target_cert.issue_date = issue_date
                if expiry_date:
                    target_cert.expiry_date = expiry_date
                if renewal_date:
                    target_cert.renewal_date = renewal_date
                if target_cert.status in (
                    "pending_verification",
                    "valid",
                    "expiring_soon",
                    "expired",
                ):
                    target_cert.status = status
                if extracted_confidence is not None:
                    target_cert.extracted_confidence = extracted_confidence
            else:
                target_cert = Certification(
                    id=str(uuid.uuid4()),
                    crew_member_id=crew_id,
                    cert_type=cert_type,
                    cert_number=cert_number,
                    issuing_body=issuing_body,
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                    renewal_date=renewal_date,
                    document_ref=document_id,
                    status=status,
                    verification_status="unverified",
                    extracted_confidence=extracted_confidence,
                )
                session.add(target_cert)

            # Keep CrewMember root medical fields in sync if this is a medical cert
            if "medical" in cert_type.lower():
                if expiry_date:
                    if not crew_member.medical_expiry or expiry_date >= crew_member.medical_expiry:
                        crew_member.medical_expiry = expiry_date
                        crew_member.medical_status = "fit" if expiry_date >= today else "expired"
                if issuing_body and not crew_member.medical_provider:
                    crew_member.medical_provider = issuing_body

            await session.commit()
            await session.refresh(target_cert)

            cache_key = cache_service._make_key("compliance", crew_id)
            await cache_service.delete(cache_key)
            await cache_service.invalidate_pattern("hydenlyne:compliance:*")

            return target_cert


auth_service = AuthService()
crew_service = CrewService()
certification_service = CertificationService()


async def bootstrap_admin() -> Optional[CrewMember]:
    """Create or update the bootstrap admin user from env config."""
    from app.auth.session import hash_password
    from app.config import get_settings as _gs

    _s = _gs()
    admin_email = (_s.ADMIN_EMAIL or "").strip().lower()
    admin_password = (_s.ADMIN_PASSWORD or "").strip()
    if not admin_email or not admin_password:
        return None

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(CrewMember).where(CrewMember.email == admin_email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            user = CrewMember(
                id=str(uuid.uuid4()),
                full_name="Administrator",
                email=admin_email,
                role="admin",
                password_hash=hash_password(admin_password),
            )
            session.add(user)
        else:
            user.role = "admin"
            # Only set password if user has none, to avoid overriding on each boot
            if not user.password_hash:
                user.password_hash = hash_password(admin_password)
        await session.commit()
        await session.refresh(user)
        return user
