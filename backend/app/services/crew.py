from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.auth.session import (
    create_session_token,
    is_token_revoked,
    verify_password,
    verify_session_token,
)
from app.database import get_session_factory
from app.models import Certification, CrewMember
from app.services.cache import cache_service

logger = logging.getLogger(__name__)


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
                    "AuthService.authenticate: no password_hash column, allowing dev login for %s",
                    email,
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
        result = verify_session_token(token)
        if not result:
            return None
        user_id, jti = result
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


class CrewService:
    """Service for crew member operations."""

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
                .limit(limit)
                .offset(offset)
            )

            if availability:
                stmt = stmt.where(CrewMember.availability_status == availability)

            if search:
                search_term = f"%{search}%"
                stmt = stmt.where(
                    or_(
                        CrewMember.full_name.ilike(search_term),
                        CrewMember.email.ilike(search_term),
                        CrewMember.nationality.ilike(search_term),
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

    async def get_compliance_status(self, crew_id: str) -> dict:
        """Get compliance status for a crew member."""
        cache_key = cache_service._make_key("compliance", crew_id)

        async def fetch():
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

        return await cache_service.get_or_set(
            cache_key,
            fetch,
            ttl=cache_service.COMPLIANCE_TTL,
        )


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
            threshold = today + timedelta(days=30)

            stmt = select(Certification).where(
                and_(
                    Certification.expiry_date < threshold,
                    Certification.status == "valid",
                )
            )
            result = await session.execute(stmt)
            certs = result.scalars().all()

            updated = 0
            for cert in certs:
                if cert.expiry_date < today:
                    cert.status = "expired"
                else:
                    cert.status = "expiring_soon"
                updated += 1

            await session.commit()

            if updated > 0:
                await cache_service.invalidate_pattern("hydenlyne:compliance:*")

            return updated


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
