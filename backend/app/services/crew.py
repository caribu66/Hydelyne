from __future__ import annotations

import logging
import math
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.session import (
    _DUMMY_PASSWORD_HASH,
    MAX_LOGIN_EMAIL_LENGTH,
    MAX_LOGIN_PASSWORD_LENGTH,
    create_session_token,
    is_token_revoked,
    verify_password,
    verify_session_token,
)
from app.database import get_session_factory
from app.domain.certifications import is_medical_cert_type, normalize_cert_name
from app.domain.crew_accounts import is_contractor_profile
from app.domain.crew_query_rules import MAX_SEARCH_QUERY_LENGTH
from app.domain.fields import (
    AVAILABILITY_STATUS_VALUES,
    CERT_STATUS_VALUES,
    CERT_VERIFICATION_STATUS_VALUES,
)
from app.domain.input_limits import validate_pagination
from app.models import Certification, CrewMember, Document, Project
from app.services.cache import cache_service
from app.services.consultant_knowledge import consultant_knowledge_service
from app.services.upload import document_upload_service

logger = logging.getLogger(__name__)

CREW_MUTABLE_FIELDS = frozenset(
    {
        "full_name",
        "email",
        "phone",
        "nationality",
        "country_of_residence",
        "date_of_birth",
        "gender",
        "languages",
        "flying_point",
        "availability_status",
        "internal_notes",
        "tags",
    }
)
CREW_BOUNDED_TEXT_FIELDS = {
    "full_name": 255,
    "email": 255,
    "phone": 50,
    "nationality": 100,
    "country_of_residence": 100,
    "gender": 50,
    "flying_point": 255,
}
MAX_CREW_LIST_ITEMS = 100
MAX_CREW_LIST_VALUE_LENGTH = 255


def _contains_like(value: str) -> str:
    """Build a literal substring pattern for a SQL ``LIKE`` expression."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _bounded_extracted_text(value: object, max_length: int, field: str) -> str | None:
    """Accept only bounded scalar text from untrusted extraction output."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        if normalized:
            logger.warning("Ignoring oversized extracted %s value", field)
        return None
    return normalized


def _extracted_certification_status(expiry_date: date | None, verification_status: str) -> str:
    """Derive a certificate lifecycle status without bypassing verification."""
    if verification_status != "verified":
        return "pending_verification"
    today = date.today()
    if expiry_date is None:
        return "valid"
    if expiry_date < today:
        return "expired"
    if expiry_date <= today + timedelta(days=30):
        return "expiring_soon"
    return "valid"


def _counts_as_valid_certification(
    expiry_date: date | None,
    verification_status: str | None,
    reference_date: date,
) -> bool:
    """Apply the dashboard's verified and beyond-30-day validity rule."""
    return verification_status == "verified" and (
        expiry_date is None or expiry_date > reference_date + timedelta(days=30)
    )


def _validate_boolean_flag(value: object, field: str) -> bool:
    """Reject truthy non-booleans before a control flag changes behavior."""
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _validate_availability_status(value: object) -> str:
    """Validate the persisted crew availability vocabulary."""
    if not isinstance(value, str) or value not in AVAILABILITY_STATUS_VALUES:
        raise ValueError(f"Invalid availability status: {value}")
    return value


def _validate_crew_update_values(updates: dict[str, object]) -> None:
    """Validate bounded crew fields before ORM assignment."""
    for field, maximum in CREW_BOUNDED_TEXT_FIELDS.items():
        value = updates.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        if not value.strip() and field == "full_name":
            raise ValueError("full_name must not be empty")
        if len(value) > maximum:
            raise ValueError(f"{field} must be {maximum} characters or fewer")
    for field in ("languages", "tags"):
        value = updates.get(field)
        if value is None:
            continue
        if not isinstance(value, list) or len(value) > MAX_CREW_LIST_ITEMS:
            raise ValueError(f"{field} must contain at most {MAX_CREW_LIST_ITEMS} values")
        if any(not isinstance(item, str) for item in value):
            raise ValueError(f"{field} values must be strings")
        if any(len(item) > MAX_CREW_LIST_VALUE_LENGTH for item in value):
            raise ValueError(
                f"{field} values must be {MAX_CREW_LIST_VALUE_LENGTH} characters or fewer"
            )


def _validate_new_crew_role(role: object) -> None:
    """Prevent profile creation from becoming account-role provisioning."""
    if role is not None and role != "user":
        raise ValueError("New crew members cannot be created with privileged roles")


def _availability_date_for_update(status: str, available_date: Optional[date]) -> Optional[date]:
    """Keep availability status and date mutually consistent."""
    if status == "on_assignment" and available_date is None:
        raise ValueError("available_date is required when status is on_assignment")
    return available_date if status == "on_assignment" else None


async def _clear_cache_keys_best_effort(*keys: str) -> None:
    """Do not turn a committed mutation into an error during cache outage."""
    for key in keys:
        try:
            if not await cache_service.delete(key):
                logger.warning("Cache invalidation was not confirmed")
        except Exception as exc:
            logger.warning("Could not invalidate cache (%s)", type(exc).__name__)


class PossibleDuplicateError(ValueError):
    def __init__(self, candidate_id: str):
        self.candidate_id = candidate_id
        super().__init__("A possible duplicate specialist already exists")


class AuthService:
    """Service for authentication and session management."""

    async def authenticate(self, email: str, password: str) -> Optional[dict]:
        """Authenticate a user and return session data."""
        if len(email) > MAX_LOGIN_EMAIL_LENGTH or len(password) > MAX_LOGIN_PASSWORD_LENGTH:
            return None
        factory = get_session_factory()
        async with factory() as session:
            canonical_email = email.strip().lower()
            stmt = (
                select(CrewMember)
                .where(func.lower(func.trim(CrewMember.email)) == canonical_email)
                .limit(2)
            )
            result = await session.execute(stmt)
            matching_users = list(result.scalars().all())
            # Admin duplicate override intentionally permits distinct profile
            # rows, but authentication must never choose an arbitrary account
            # when their login identifier is ambiguous.
            user = matching_users[0] if len(matching_users) == 1 else None

            if not user:
                verify_password(password, _DUMMY_PASSWORD_HASH)
                return None

            # Legacy rows may still lack a password hash. Never fall back to a
            # predictable credential; passwordless login is an explicit local
            # development opt-in below.
            stored = getattr(user, "password_hash", None)
            if stored:
                if not verify_password(password, stored):
                    return None
            else:
                # No password column yet: use constant-time dummy check to avoid
                # timing oracle, but require explicit env flag to allow passwordless
                # login in development only. Default: deny.
                from app.config import get_settings as _gs

                settings = _gs()
                if settings.APP_ENV != "development" or not settings.ALLOW_PASSWORDLESS_DEV_LOGIN:
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
        as_draft: bool,
        submitted_by: str | None = None,
        allow_duplicate: bool = False,
    ) -> CrewMember:
        """Persist a new crew member and index them for retrieval.

        ``crew`` is an unpersisted model instance built by the caller (the
        GraphQL layer owns mapping the create DTO to a model).
        """
        _validate_new_crew_role(crew.role)
        _validate_crew_update_values(
            {
                "full_name": crew.full_name,
                "email": crew.email,
                "phone": crew.phone,
                "nationality": crew.nationality,
                "country_of_residence": crew.country_of_residence,
                "gender": crew.gender,
                "flying_point": crew.flying_point,
                "languages": crew.languages,
                "tags": crew.tags,
            }
        )
        if crew.availability_status is not None:
            _validate_availability_status(crew.availability_status)
        _validate_boolean_flag(as_draft, "as_draft")
        _validate_boolean_flag(allow_duplicate, "allow_duplicate")
        factory = get_session_factory()
        async with factory() as session:
            if as_draft:
                if not allow_duplicate:
                    conditions = [
                        func.lower(func.trim(CrewMember.full_name))
                        == crew.full_name.strip().lower()
                    ]
                    if crew.email:
                        conditions.append(
                            func.lower(func.trim(CrewMember.email)) == crew.email.strip().lower()
                        )
                    duplicate = (
                        await session.execute(
                            select(CrewMember.id).where(or_(*conditions)).limit(1)
                        )
                    ).scalar_one_or_none()
                    if duplicate is not None:
                        raise PossibleDuplicateError(duplicate)
                crew.publication_status = "draft"
                crew.submitted_by = submitted_by
            session.add(crew)
            await session.commit()
            crew = await _reload_crew_with_relations(session, crew.id)

        if crew.publication_status == "approved":
            try:
                if not await consultant_knowledge_service.index_crew_member(crew):
                    raise RuntimeError("crew indexing was not confirmed")
            except Exception as exc:
                logger.warning("Could not index created crew member (%s)", type(exc).__name__)
                from app.tasks.document_tasks import queue_crew_projection_reconcile

                queue_crew_projection_reconcile(crew.id)
        return crew

    async def update_crew_member(self, crew_id: str, updates: dict[str, object]) -> CrewMember:
        """Apply the given field updates to a crew member.

        ``updates`` should contain only fields the caller actually wants
        changed (already filtered of unset/None values). Only profile fields
        are mutable here; role and publication workflow state have dedicated
        authorization-aware services.
        """
        if not isinstance(updates, dict):
            raise ValueError("Crew member updates must be an object")
        unexpected_fields = set(updates) - CREW_MUTABLE_FIELDS
        if unexpected_fields:
            raise ValueError(
                "Unsupported crew member update fields: "
                + ", ".join(sorted(unexpected_fields))
            )
        _validate_crew_update_values(updates)
        if "availability_status" in updates:
            _validate_availability_status(updates["availability_status"])
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
            result = await session.execute(stmt)
            crew = result.scalar_one_or_none()
            if not crew or not is_contractor_profile(crew):
                raise ValueError(f"Crew member {crew_id} not found")
            if "availability_status" in updates:
                availability_status = _validate_availability_status(updates["availability_status"])
                updates = {
                    **updates,
                    "availability_date": _availability_date_for_update(
                        availability_status, crew.availability_date
                    ),
                }
            for field, value in updates.items():
                setattr(crew, field, value)
            await session.commit()
            crew = await _reload_crew_with_relations(session, crew.id)

        if crew.publication_status == "approved":
            try:
                if not await consultant_knowledge_service.index_crew_member(crew):
                    raise RuntimeError("crew indexing was not confirmed")
            except Exception as exc:
                logger.warning("Could not index updated crew member (%s)", type(exc).__name__)
                from app.tasks.document_tasks import queue_crew_projection_reconcile

                queue_crew_projection_reconcile(crew.id)
        else:
            try:
                if not await consultant_knowledge_service.remove_from_index(crew.id):
                    raise RuntimeError("crew removal was not confirmed")
            except Exception as exc:
                logger.warning(
                    "Could not remove updated crew member projection (%s)", type(exc).__name__
                )
                from app.tasks.document_tasks import queue_crew_projection_reconcile

                queue_crew_projection_reconcile(crew.id)
        # The AI summary is generated from these same fields — a stale
        # cached summary after an edit would show outdated facts.
        await _clear_cache_keys_best_effort(cache_service._make_key("summary", crew.id))
        return crew

    async def set_staff_role(self, crew_id: str, *, enabled: bool) -> CrewMember:
        """Promote or demote a non-admin account without altering admin accounts."""
        _validate_boolean_flag(enabled, "enabled")
        factory = get_session_factory()
        async with factory() as session:
            crew = (
                await session.execute(
                    select(CrewMember)
                    .options(selectinload(CrewMember.documents))
                    .where(CrewMember.id == crew_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if crew is None:
                raise ValueError("User not found")
            if crew.role == "admin":
                raise ValueError("Administrator roles cannot be changed here")
            crew.role = "staff" if enabled else "user"
            document_ids = [document.id for document in crew.documents]
            await session.commit()
            await _clear_cache_keys_best_effort(
                cache_service._make_key("summary", crew.id),
                cache_service._make_key("compliance", crew.id),
            )

            # Role changes alter projection eligibility. Reconcile after the
            # source commit so a contractor promoted to an account cannot
            # remain discoverable through a stale search/vector projection.
            cleanup_required = False
            try:
                if not await consultant_knowledge_service.remove_from_index(crew.id):
                    cleanup_required = True
            except Exception as exc:
                cleanup_required = True
                logger.warning(
                    "Could not remove role-changed account from search (%s)",
                    type(exc).__name__,
                )
            from app.config import get_settings

            if get_settings().ENABLE_SEMANTIC_SEARCH:
                from app.services.qdrant import qdrant_service

                for document_id in document_ids:
                    try:
                        if not await qdrant_service.delete_document(document_id):
                            cleanup_required = True
                    except Exception as exc:
                        cleanup_required = True
                        logger.warning(
                            "Could not remove role-changed account vector (%s)",
                            type(exc).__name__,
                        )
            if cleanup_required:
                from app.tasks.document_tasks import queue_deleted_crew_projection_cleanup

                queue_deleted_crew_projection_cleanup(crew.id, document_ids)
            return await _reload_crew_with_relations(session, crew.id)

    async def delete_crew_member(self, crew_id: str, requesting_user_id: Optional[str]) -> bool:
        """Permanently delete a crew member and their managed documents.

        Admin-only by decorator. Database metadata is removed before remote
        cleanup so a failed transaction cannot leave a live row pointing at a
        missing Dropbox original. Failed remote cleanup is queued for retry.
        """
        if requesting_user_id == crew_id:
            raise ValueError("You cannot delete your own administrator account")

        factory = get_session_factory()
        async with factory() as session:
            # Document workflows lock document -> contractor while detaching
            # certifications and refreshing the medical projection. Acquire
            # the same locks in that order here to avoid a delete/revision
            # deadlock.
            documents_result = await session.execute(
                select(Document)
                .where(Document.crew_member_id == crew_id)
                .with_for_update()
            )
            documents = list(documents_result.scalars().all())
            document_cleanup = [
                (document.id, document.storage_path, document.storage_type, document.dropbox_path)
                for document in documents
            ]
            stmt = select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
            result = await session.execute(stmt)
            crew = result.scalar_one_or_none()
            if not crew:
                return False

            # Projects retain a backwards-compatible JSON assignment list in
            # addition to normalized CampaignAssignment rows. Remove the
            # deleted contractor from both sources in the same transaction so
            # project readiness cannot retain an orphaned ID.
            projects_result = await session.execute(
                select(Project)
                .where(Project.crew_assigned.is_not(None))
                .with_for_update()
            )
            for project in projects_result.scalars():
                assigned_ids = project.crew_assigned
                if isinstance(assigned_ids, list) and crew_id in assigned_ids:
                    project.crew_assigned = [
                        assigned_id for assigned_id in assigned_ids if assigned_id != crew_id
                    ]

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
        cleanup_required = False
        for _, storage_path, storage_type, dropbox_path in document_cleanup:
            if storage_type == "dropbox":
                remote_deleted = bool(
                    dropbox_path
                    and await document_upload_service.delete_from_dropbox(dropbox_path)
                )
                if not remote_deleted:
                    cleanup_required = True
                    logger.warning("Could not remove deleted crew document from Dropbox")
                    from app.tasks.document_tasks import queue_orphaned_upload_cleanup

                    queue_orphaned_upload_cleanup("dropbox", dropbox_path or storage_path)
            try:
                document_upload_service.delete_file(storage_path)
            except Exception as exc:
                cleanup_required = True
                logger.warning(
                    "Could not remove deleted crew document cache (%s)", type(exc).__name__
                )
                from app.tasks.document_tasks import queue_local_document_cache_cleanup

                queue_local_document_cache_cleanup(storage_path)

        from app.config import get_settings

        if get_settings().ENABLE_SEMANTIC_SEARCH:
            from app.services.qdrant import qdrant_service

            for document_id, _, _, _ in document_cleanup:
                try:
                    if not await qdrant_service.delete_document(document_id):
                        cleanup_required = True
                        logger.warning("Deleted crew vector cleanup was not confirmed")
                except Exception as exc:
                    cleanup_required = True
                    logger.warning(
                        "Could not remove deleted crew document vector (%s)",
                        type(exc).__name__,
                    )

        for cache_key in (
            cache_service._make_key("crew", crew_id),
            cache_service._make_key("summary", crew_id),
            cache_service._make_key("compliance", crew_id),
        ):
            try:
                if not await cache_service.delete(cache_key):
                    cleanup_required = True
                    logger.warning("Cache invalidation was not confirmed for deleted crew")
            except Exception as exc:
                cleanup_required = True
                logger.warning("Could not clear deleted crew cache (%s)", type(exc).__name__)
        try:
            if not await consultant_knowledge_service.remove_from_index(crew_id):
                cleanup_required = True
                logger.warning("Deleted crew search cleanup was not confirmed")
        except Exception as exc:
            cleanup_required = True
            logger.warning(
                "Could not remove deleted crew search projection (%s)", type(exc).__name__
            )
        if cleanup_required:
            from app.tasks.document_tasks import queue_deleted_crew_projection_cleanup

            queue_deleted_crew_projection_cleanup(
                crew_id,
                [document_id for document_id, _, _, _ in document_cleanup],
            )
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

    async def can_access_profile(
        self, crew_id: str, *, actor_id: Optional[str], actor_role: str
    ) -> bool:
        """Drafts are visible only to their submitter and administrators."""
        factory = get_session_factory()
        async with factory() as session:
            crew = (
                await session.execute(select(CrewMember).where(CrewMember.id == crew_id))
            ).scalar_one_or_none()
            return bool(
                crew
                and (
                    (is_contractor_profile(crew) or actor_role == "admin" or crew.id == actor_id)
                    and (
                        crew.publication_status == "approved"
                        or actor_role == "admin"
                        or (
                            crew.publication_status == "draft"
                            and actor_id is not None
                            and crew.submitted_by == actor_id
                        )
                    )
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
        if search is not None:
            if not isinstance(search, str):
                raise ValueError("Search query must be a string")
            search = search.strip()
            if not search:
                raise ValueError("Search query must not be blank")
            if len(search) > MAX_SEARCH_QUERY_LENGTH:
                raise ValueError(
                    f"Search query must be {MAX_SEARCH_QUERY_LENGTH} characters or fewer"
                )
        limit, offset = validate_pagination(limit, offset)
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
                .order_by(CrewMember.created_at.desc(), CrewMember.id.desc())
                .limit(limit)
                .offset(offset)
                .where(CrewMember.publication_status == "approved")
                # Login accounts share this table but are managed through the
                # staff_accounts surface, not contractor discovery. Legacy
                # contractor rows may use a profession in ``role``.
                .where(
                    or_(
                        CrewMember.role.is_(None),
                        CrewMember.role.not_in(("staff", "admin")),
                    )
                )
                .where(CrewMember.password_hash.is_(None))
            )

            if availability:
                stmt = stmt.where(CrewMember.availability_status == availability)

            if search:
                search_term = _contains_like(search.strip())
                stmt = stmt.where(
                    or_(
                        CrewMember.full_name.ilike(search_term, escape="\\"),
                        CrewMember.nationality.ilike(search_term, escape="\\"),
                        CrewMember.country_of_residence.ilike(search_term, escape="\\"),
                        cast(CrewMember.languages, String).ilike(search_term, escape="\\"),
                        CrewMember.flying_point.ilike(search_term, escape="\\"),
                        CrewMember.education.ilike(search_term, escape="\\"),
                        CrewMember.professional_summary.ilike(search_term, escape="\\"),
                        cast(CrewMember.geographical_experience, String).ilike(
                            search_term, escape="\\"
                        ),
                        cast(CrewMember.systems_experience, String).ilike(
                            search_term, escape="\\"
                        ),
                        cast(CrewMember.training_qualifications, String).ilike(
                            search_term, escape="\\"
                        ),
                        cast(CrewMember.tags, String).ilike(search_term, escape="\\"),
                        CrewMember.certifications.any(
                            and_(
                                Certification.cert_type.ilike(search_term, escape="\\"),
                                or_(
                                    Certification.status.is_(None),
                                    Certification.status != "rejected",
                                ),
                                or_(
                                    Certification.verification_status.is_(None),
                                    Certification.verification_status != "rejected",
                                ),
                            )
                        ),
                    )
                )

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_staff_accounts(self, limit: int = 100, offset: int = 0) -> list[CrewMember]:
        """List all account records for administrator staff management.

        Account eligibility is independent of contractor publication status;
        draft and rejected profiles must remain manageable by administrators.
        """
        limit, offset = validate_pagination(limit, offset)
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(CrewMember)
                .options(
                    selectinload(CrewMember.certifications),
                    selectinload(CrewMember.work_history),
                    selectinload(CrewMember.documents),
                )
                .order_by(CrewMember.created_at.desc(), CrewMember.id.desc())
                .limit(limit)
                .offset(offset)
                # Staff management is an account surface, not a second
                # contractor roster. Include legacy role-marked accounts even
                # when their password column is null, but exclude ordinary
                # passwordless contractor profiles.
                .where(
                    or_(
                        CrewMember.password_hash.is_not(None),
                        CrewMember.role.in_(("staff", "admin")),
                    )
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
        validated_status = _validate_availability_status(status)
        validated_date = _availability_date_for_update(validated_status, available_date)
        factory = get_session_factory()
        async with factory() as session:
            # Availability is also maintained by assignment transitions. Lock
            # the profile so a manual update cannot overwrite a concurrent
            # assignment-derived availability value with a stale read.
            stmt = select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
            result = await session.execute(stmt)
            crew = result.scalar_one_or_none()

            if not crew or not is_contractor_profile(crew):
                return None

            crew.availability_status = validated_status
            crew.availability_date = validated_date

            await session.commit()
            await session.refresh(crew)

            await _clear_cache_keys_best_effort(
                cache_service._make_key("crew", crew_id),
                cache_service._make_key("summary", crew_id),
            )
            if crew.publication_status == "approved":
                try:
                    if not await consultant_knowledge_service.index_crew_member(crew):
                        raise RuntimeError("crew indexing was not confirmed")
                except Exception as exc:
                    logger.warning("Could not index availability update (%s)", type(exc).__name__)
                    from app.tasks.document_tasks import queue_crew_projection_reconcile

                    queue_crew_projection_reconcile(crew.id)
            else:
                try:
                    if not await consultant_knowledge_service.remove_from_index(crew_id):
                        raise RuntimeError("crew removal was not confirmed")
                except Exception as exc:
                    logger.warning(
                        "Could not remove availability projection (%s)", type(exc).__name__
                    )
                    from app.tasks.document_tasks import queue_crew_projection_reconcile

                    queue_crew_projection_reconcile(crew.id)

            return crew

    async def get_compliance_status(self, crew_id: str) -> dict[str, Any]:
        """Get compliance status for a crew member."""
        empty_status = {
            "total": 0,
            "valid": 0,
            "expiring_soon": 0,
            "expired": 0,
            "pending_verification": 0,
        }
        factory = get_session_factory()
        async with factory() as revision_session:
            crew_result = await revision_session.execute(
                select(CrewMember).where(CrewMember.id == crew_id)
            )
            crew = crew_result.scalar_one_or_none()
            if crew is None or not is_contractor_profile(crew):
                return empty_status
            revision_rows = await revision_session.execute(
                select(
                    Certification.id,
                    Certification.updated_at,
                    Certification.expiry_date,
                    Certification.status,
                    Certification.verification_status,
                )
                .where(Certification.crew_member_id == crew_id)
                .order_by(Certification.id)
            )
            cache_revision = [tuple(row) for row in revision_rows.all()]
        cache_key = cache_service._make_key("compliance", crew_id, revision=cache_revision)

        async def fetch() -> dict[str, Any]:
            async with factory() as session:
                stmt = select(Certification).where(
                    Certification.crew_member_id == crew_id,
                    or_(
                        Certification.status.is_(None),
                        Certification.status != "rejected",
                    ),
                    or_(
                        Certification.verification_status.is_(None),
                        Certification.verification_status != "rejected",
                    ),
                )
                result = await session.execute(stmt)
                certs = result.scalars().all()

                today = date.today()
                return {
                    "total": len(certs),
                    "valid": sum(
                        1
                        for c in certs
                        if _counts_as_valid_certification(
                            c.expiry_date, c.verification_status, today
                        )
                    ),
                    "expiring_soon": sum(
                        1
                        for c in certs
                        if c.verification_status == "verified"
                        and c.expiry_date
                        and c.expiry_date <= today + timedelta(days=30)
                        and c.expiry_date >= today
                    ),
                    "expired": sum(
                        1
                        for c in certs
                        if c.verification_status == "verified"
                        and c.expiry_date
                        and c.expiry_date < today
                    ),
                    "pending_verification": sum(
                        1
                        for c in certs
                        if c.verification_status in {None, "unverified"}
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

    @staticmethod
    async def _lock_certification_and_owner(
        session: AsyncSession, cert_id: str
    ) -> Certification:
        """Lock the owner before the evidence row to match ingestion lock order."""
        owner_result = await session.execute(
            select(Certification.crew_member_id).where(Certification.id == cert_id)
        )
        owner_id = owner_result.scalar_one_or_none()
        if owner_id is None:
            raise ValueError(f"Certification {cert_id} not found")

        owner_result = await session.execute(
            select(CrewMember).where(CrewMember.id == owner_id).with_for_update()
        )
        owner = owner_result.scalar_one_or_none()
        if owner is None or not is_contractor_profile(owner):
            raise ValueError(f"Certification {cert_id} not found")
        locked_result = await session.execute(
            select(Certification).where(Certification.id == cert_id).with_for_update()
        )
        certification = locked_result.scalar_one_or_none()
        if certification is None:
            raise ValueError(f"Certification {cert_id} not found")
        return certification

    @staticmethod
    def _validate_certification_dates(
        issue_date: object,
        expiry_date: object,
    ) -> None:
        if issue_date is not None and (
            not isinstance(issue_date, date) or isinstance(issue_date, datetime)
        ):
            raise ValueError("issue_date must be a date")
        if expiry_date is not None and (
            not isinstance(expiry_date, date) or isinstance(expiry_date, datetime)
        ):
            raise ValueError("expiry_date must be a date")
        if (
            isinstance(issue_date, date)
            and isinstance(expiry_date, date)
            and issue_date > expiry_date
        ):
            raise ValueError("issue_date must be on or before expiry_date")

    @staticmethod
    def _validate_certification_text(
        cert_type: str,
        cert_number: Optional[str],
        issuing_body: Optional[str],
    ) -> None:
        if not isinstance(cert_type, str) or not cert_type.strip():
            raise ValueError("cert_type must not be empty")
        if len(cert_type) > 50:
            raise ValueError("cert_type must be 50 characters or fewer")
        if cert_number is not None and not isinstance(cert_number, str):
            raise ValueError("cert_number must be a string")
        if cert_number is not None and len(cert_number) > 100:
            raise ValueError("cert_number must be 100 characters or fewer")
        if issuing_body is not None and not isinstance(issuing_body, str):
            raise ValueError("issuing_body must be a string")
        if issuing_body is not None and len(issuing_body) > 255:
            raise ValueError("issuing_body must be 255 characters or fewer")

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
        self._validate_certification_text(cert_type, cert_number, issuing_body)
        self._validate_certification_dates(issue_date, expiry_date)
        factory = get_session_factory()
        async with factory() as session:
            crew = (
                await session.execute(
                    select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
                )
            ).scalar_one_or_none()
            if crew is None or not is_contractor_profile(crew):
                raise ValueError("Crew member not found")
            status = _extracted_certification_status(expiry_date, "verified")
            cert = Certification(
                crew_member_id=crew_id,
                cert_type=cert_type,
                cert_number=cert_number,
                issuing_body=issuing_body,
                issue_date=issue_date,
                expiry_date=expiry_date,
                status=status,
                verification_status="verified",
            )
            session.add(cert)
            if is_medical_cert_type(cert_type):
                from app.services.certification_projection import reconcile_medical_profile

                await reconcile_medical_profile(session, crew_id=crew_id)
                crew = await session.get(CrewMember, crew_id)
                if crew is not None and issuing_body and not crew.medical_provider:
                    crew.medical_provider = issuing_body
            await session.commit()
            await session.refresh(cert)

            await _clear_cache_keys_best_effort(
                cache_service._make_key("compliance", crew_id),
                cache_service._make_key("summary", crew_id),
            )

            return cert

    async def update_certification(
        self, cert_id: str, status: Optional[str] = None
    ) -> Certification:
        """Update a certification's status."""
        if status is not None and (
            not isinstance(status, str) or status not in CERT_STATUS_VALUES
        ):
            raise ValueError(f"Invalid certification status: {status}")
        factory = get_session_factory()
        async with factory() as session:
            cert = await self._lock_certification_and_owner(session, cert_id)
            if status is not None:
                cert.status = (
                    "pending_verification"
                    if status == "valid" and cert.verification_status != "verified"
                    else status
                )
            if is_medical_cert_type(cert.cert_type):
                from app.services.certification_projection import reconcile_medical_profile

                await reconcile_medical_profile(session, crew_id=cert.crew_member_id)
            await session.commit()
            await session.refresh(cert)
            await _clear_cache_keys_best_effort(
                cache_service._make_key("compliance", cert.crew_member_id),
                cache_service._make_key("summary", cert.crew_member_id),
            )
            return cert

    async def verify_certification(self, cert_id: str, status: str) -> Certification:
        """Set a certification's verification status and update lifecycle status."""
        if not isinstance(status, str) or status not in CERT_VERIFICATION_STATUS_VALUES:
            raise ValueError(f"Invalid certification verification status: {status}")
        factory = get_session_factory()
        async with factory() as session:
            cert = await self._lock_certification_and_owner(session, cert_id)
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
            elif status == "unverified":
                cert.status = "pending_verification"

            if is_medical_cert_type(cert.cert_type):
                from app.services.certification_projection import reconcile_medical_profile

                await reconcile_medical_profile(session, crew_id=cert.crew_member_id)

            await session.commit()
            await session.refresh(cert)

            await _clear_cache_keys_best_effort(
                cache_service._make_key("compliance", cert.crew_member_id),
                cache_service._make_key("summary", cert.crew_member_id),
            )

            return cert

    async def get_expiring_certifications(
        self,
        days: int = 30,
        limit: int = 100,
        offset: int = 0,
        *,
        actor_id: str | None = None,
        actor_role: str = "user",
    ) -> list[Certification]:
        """Get visible certifications expiring within the specified days."""
        if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 365:
            raise ValueError("days must be an integer between 1 and 365")
        limit, offset = validate_pagination(limit, offset)
        factory = get_session_factory()
        async with factory() as session:
            threshold = date.today() + timedelta(days=days)
            stmt = (
                select(Certification)
                .join(CrewMember, Certification.crew_member_id == CrewMember.id)
                .where(
                    and_(
                        Certification.expiry_date <= threshold,
                        Certification.expiry_date >= date.today(),
                        CrewMember.password_hash.is_(None),
                        or_(
                            CrewMember.role.is_(None),
                            CrewMember.role.not_in(("staff", "admin")),
                        ),
                        or_(
                            Certification.status.is_(None),
                            Certification.status != "rejected",
                        ),
                        Certification.verification_status == "verified",
                    )
                )
                .options(selectinload(Certification.crew_member))
            )
            if actor_role != "admin":
                if actor_role == "staff" and actor_id:
                    stmt = stmt.where(
                        or_(
                            CrewMember.publication_status == "approved",
                            and_(
                                CrewMember.publication_status == "draft",
                                CrewMember.submitted_by == actor_id,
                            ),
                        )
                    )
                else:
                    stmt = stmt.where(CrewMember.publication_status == "approved")
            stmt = stmt.order_by(Certification.expiry_date.asc(), Certification.id.asc())
            stmt = stmt.limit(limit).offset(offset)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def check_and_update_expiration_status(self) -> int:
        """Update status of certifications based on expiration dates in bounded batches."""
        factory = get_session_factory()
        async with factory() as session:
            today = date.today()
            updated = 0
            affected_crew_ids: set[str] = set()
            last_id = ""

            batch_size = 200
            while True:
                stmt = (
                    select(Certification)
                    .join(CrewMember, Certification.crew_member_id == CrewMember.id)
                    .where(
                        CrewMember.password_hash.is_(None),
                        or_(
                            CrewMember.role.is_(None),
                            CrewMember.role.not_in(("staff", "admin")),
                        ),
                        Certification.expiry_date.isnot(None),
                        or_(
                            Certification.status.is_(None),
                            Certification.status != "rejected",
                        ),
                        or_(
                            Certification.verification_status.is_(None),
                            Certification.verification_status != "rejected",
                        ),
                        Certification.id > last_id,
                    )
                    .options(selectinload(Certification.crew_member))
                    .order_by(Certification.id)
                    .limit(batch_size)
                    .with_for_update()
                )
                result = await session.execute(stmt)
                certs = result.scalars().all()
                if not certs:
                    break

                for cert in certs:
                    if cert.expiry_date is None:
                        continue
                    old_status = cert.status
                    new_status: Optional[str] = None
                    days_remaining = (cert.expiry_date - today).days
                    if days_remaining < 0:
                        target_status = "expired"
                    elif days_remaining <= 30:
                        target_status = "expiring_soon"
                    else:
                        target_status = "valid"
                    if cert.status in {"valid", "expiring_soon", "expired"}:
                        if cert.status != target_status:
                            new_status = target_status

                    if new_status and new_status != old_status:
                        cert.status = new_status
                        updated += 1
                        if cert.crew_member:
                            affected_crew_ids.add(cert.crew_member.id)

                await session.commit()
                last_id = certs[-1].id

            if affected_crew_ids:
                from app.services.certification_projection import reconcile_medical_profile

                for crew_id in affected_crew_ids:
                    await reconcile_medical_profile(session, crew_id=crew_id)
                await session.commit()

            for crew_id in affected_crew_ids:
                await _clear_cache_keys_best_effort(
                    cache_service._make_key("compliance", crew_id),
                    cache_service._make_key("summary", crew_id),
                )

            return updated

    @staticmethod
    def _parse_date(date_val: Any) -> Optional[date]:
        """Safely parse date strings or objects into a datetime.date."""
        if not date_val:
            return None
        if isinstance(date_val, datetime):
            return date_val.date()
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
        expected_extracted_data: Optional[dict[str, Any]] = None,
    ) -> Optional[Certification]:
        """Auto-create or update a Certification row from extracted certificate document data.

        Links the Certification record to the backing Document via document_ref.
        If a matching unlinked certification already exists (e.g. from CV ingestion),
        it updates it with the verified document reference and new date/number evidence.
        """
        if not isinstance(extracted_data, dict):
            raise ValueError("Extracted certificate data must be a JSON object")
        raw_cert_type = (
            extracted_data.get("certificate_type")
            or extracted_data.get("cert_type")
            or extracted_data.get("title")
            or extracted_data.get("name")
        )
        if not isinstance(raw_cert_type, str):
            logger.warning("Ignoring malformed certificate type in document %s", document_id)
            return None
        if not raw_cert_type.strip():
            logger.info(f"No certificate type identified in document {document_id}")
            return None

        cert_type = normalize_cert_name(str(raw_cert_type))
        if len(cert_type) > 50:
            logger.warning("Ignoring oversized certificate type in document %s", document_id)
            return None

        cert_number = _bounded_extracted_text(
            extracted_data.get("certificate_number") or extracted_data.get("cert_number"),
            100,
            "certificate_number",
        )

        issuing_body = extracted_data.get("issuing_body") or extracted_data.get("training_provider")
        issuing_body = _bounded_extracted_text(issuing_body, 255, "issuing_body")

        issue_date = self._parse_date(extracted_data.get("issue_date"))
        expiry_date = self._parse_date(extracted_data.get("expiry_date"))
        renewal_date = self._parse_date(extracted_data.get("renewal_date"))
        if issue_date and expiry_date and expiry_date < issue_date:
            logger.warning("Ignoring reversed extracted certification expiry date")
            expiry_date = None

        raw_confidence = confidence or extracted_data.get("confidence")
        extracted_confidence: Optional[float] = None
        if isinstance(raw_confidence, dict):
            numeric_scores = [
                float(value)
                for value in raw_confidence.values()
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(float(value))
                    and 0.0 <= float(value) <= 1.0
                )
            ]
            if numeric_scores:
                extracted_confidence = round(sum(numeric_scores) / len(numeric_scores), 2)
        elif (
            isinstance(raw_confidence, (int, float))
            and not isinstance(raw_confidence, bool)
            and math.isfinite(float(raw_confidence))
            and 0.0 <= float(raw_confidence) <= 1.0
        ):
            extracted_confidence = round(float(raw_confidence), 2)

        # Lifecycle warnings (expired/expiring_soon) describe calendar facts
        # evidenced in the linked document and display freely; a positive
        # "valid" claim requires administrator verification (same demotion
        # as update_certification), so it stays pending_verification here.
        # Trust itself remains in verification_status, which compliance
        # checks gate on independently.
        evidenced_status = _extracted_certification_status(expiry_date, "verified")
        status = evidenced_status if evidenced_status != "valid" else "pending_verification"

        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(CrewMember)
                .options(selectinload(CrewMember.certifications))
                .where(CrewMember.id == crew_id)
                .with_for_update()
            )
            document = (
                await session.execute(
                    select(Document).where(Document.id == document_id).with_for_update()
                )
            ).scalar_one_or_none()
            if document is None:
                logger.warning("Certificate document %s no longer exists", document_id)
                return None
            if document.crew_member_id != crew_id:
                logger.warning(
                    "Certificate document %s is linked to another crew member", document_id
                )
                return None
            if document.extraction_status not in {"extracted", "approved"}:
                return None
            if (
                document.uploaded_by == "contractor-upload-link"
                and document.extraction_status != "approved"
            ):
                return None
            if (
                expected_extracted_data is not None
                and document.extracted_data != expected_extracted_data
            ):
                logger.info(
                    "Skipping stale certificate projection for document %s", document_id
                )
                return None
            result = await session.execute(stmt)
            crew_member = result.scalar_one_or_none()
            if crew_member is None or not is_contractor_profile(crew_member):
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
                same_document = target_cert.document_ref == document_id
                previous_values = (
                    target_cert.cert_type,
                    target_cert.cert_number,
                    target_cert.issuing_body,
                    target_cert.issue_date,
                    target_cert.expiry_date,
                    target_cert.renewal_date,
                )
                was_verified = target_cert.verification_status == "verified"
                target_cert.document_ref = document_id
                target_cert.cert_type = cert_type
                if (
                    same_document
                    or "certificate_number" in extracted_data
                    or "cert_number" in extracted_data
                ):
                    target_cert.cert_number = cert_number
                if (
                    same_document
                    or "issuing_body" in extracted_data
                    or "training_provider" in extracted_data
                ):
                    target_cert.issuing_body = issuing_body
                if same_document or "issue_date" in extracted_data:
                    target_cert.issue_date = issue_date
                if same_document or "expiry_date" in extracted_data:
                    target_cert.expiry_date = expiry_date
                if same_document or "renewal_date" in extracted_data:
                    target_cert.renewal_date = renewal_date
                if extracted_confidence is not None:
                    target_cert.extracted_confidence = extracted_confidence
                current_values = (
                    target_cert.cert_type,
                    target_cert.cert_number,
                    target_cert.issuing_body,
                    target_cert.issue_date,
                    target_cert.expiry_date,
                    target_cert.renewal_date,
                )
                if current_values != previous_values or target_cert.verification_status == "rejected":
                    target_cert.verification_status = "unverified"
                target_cert.status = (
                    _extracted_certification_status(
                        target_cert.expiry_date, "verified" if was_verified else "unverified"
                    )
                    if current_values == previous_values
                    else status
                )
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

            # Keep CrewMember root medical fields in sync if this is a medical cert.
            if is_medical_cert_type(cert_type):
                from app.services.certification_projection import reconcile_medical_profile

                await reconcile_medical_profile(session, crew_id=crew_id)
                if issuing_body and not crew_member.medical_provider:
                    crew_member.medical_provider = issuing_body

            await session.commit()
            await session.refresh(target_cert)

            await _clear_cache_keys_best_effort(
                cache_service._make_key("compliance", crew_id),
                cache_service._make_key("summary", crew_id),
            )

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
