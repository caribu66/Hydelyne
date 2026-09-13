"""Campaign assignment service — manages consultant deployment to vessels and projects."""

from __future__ import annotations

import logging
import math
import re
import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.database import get_session_factory
from app.domain.certifications import is_medical_cert_type
from app.domain.crew_accounts import is_contractor_profile
from app.domain.input_limits import validate_pagination
from app.models import CampaignAssignment, Certification, CrewMember, Project, Vessel
from app.services.cache import cache_service
from app.services.consultant_knowledge import consultant_knowledge_service

logger = logging.getLogger(__name__)

ACTIVE_ASSIGNMENT_STATUSES = {"confirmed", "on_board"}
ASSIGNMENT_STATUSES = ACTIVE_ASSIGNMENT_STATUSES | {
    "proposed",
    "completed",
    "cancelled",
}
_VESSEL_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_ROLE_ON_BOARD_LENGTH = 100
MAX_VESSEL_NAME_LENGTH = 255
MAX_ASSIGNMENT_NOTES_LENGTH = 5000


def _normalize_vessel_imo(value: str) -> str:
    """Normalize the persisted vessel key without accepting blank records."""
    if not isinstance(value, str):
        raise ValueError("vessel_imo must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("vessel_imo must not be empty")
    if len(normalized) > 20:
        raise ValueError("vessel_imo is too long (max 20 characters)")
    if not _VESSEL_KEY_PATTERN.fullmatch(normalized):
        raise ValueError("vessel_imo contains invalid characters")
    return normalized


def _normalize_assignment_text(
    role_on_board: object,
    vessel_name: object,
    notes: object,
) -> tuple[str, str | None, str | None]:
    """Validate assignment text before any database or provider work."""
    if not isinstance(role_on_board, str) or not role_on_board.strip():
        raise ValueError("role_on_board must not be empty")
    clean_role = role_on_board.strip()
    if len(clean_role) > MAX_ROLE_ON_BOARD_LENGTH:
        raise ValueError(f"role_on_board must be {MAX_ROLE_ON_BOARD_LENGTH} characters or fewer")

    clean_vessel_name = vessel_name.strip() if isinstance(vessel_name, str) else None
    if clean_vessel_name and len(clean_vessel_name) > MAX_VESSEL_NAME_LENGTH:
        raise ValueError(f"vessel_name must be {MAX_VESSEL_NAME_LENGTH} characters or fewer")

    clean_notes = notes.strip() if isinstance(notes, str) and notes.strip() else None
    if clean_notes and len(clean_notes) > MAX_ASSIGNMENT_NOTES_LENGTH:
        raise ValueError(f"notes must be {MAX_ASSIGNMENT_NOTES_LENGTH} characters or fewer")
    return clean_role, clean_vessel_name, clean_notes


def _validate_assignment_dates(start_date: object, end_date: object) -> tuple[date, date]:
    """Require calendar dates and reject datetime values at the service boundary."""
    if (
        not isinstance(start_date, date)
        or isinstance(start_date, datetime)
        or not isinstance(end_date, date)
        or isinstance(end_date, datetime)
    ):
        raise ValueError("start_date and end_date must be dates")
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    return start_date, end_date


def _assignment_query_options() -> tuple[Any, ...]:
    """Eagerly load related models to prevent async greenlet lazy-load errors outside session."""
    return (
        selectinload(CampaignAssignment.crew_member),
        selectinload(CampaignAssignment.vessel),
        selectinload(CampaignAssignment.project),
    )


def _critical_credential_issue(
    crew: CrewMember,
    certifications: list[Certification],
    start_date: date,
) -> str | None:
    """Return a blocking availability or credential issue, if any."""
    if crew.publication_status == "rejected":
        return "Specialist profile is rejected"
    if crew.availability_status == "unavailable":
        return "Specialist is marked unavailable"
    if crew.availability_status == "on_assignment":
        if crew.availability_date is None:
            return "Specialist is already on assignment with no release date"
        if crew.availability_date >= start_date:
            return f"Specialist is on assignment through {crew.availability_date.isoformat()}"

    def is_usable_verified(certification: Certification) -> bool:
        return (
            certification.verification_status == "verified"
            and certification.status != "rejected"
        )

    verified_medical_expiries = [
        cert.expiry_date
        for cert in certifications
        if cert.expiry_date
        and cert.expiry_date < start_date
        and is_usable_verified(cert)
        and is_medical_cert_type(cert.cert_type)
    ]
    if verified_medical_expiries:
        expiry = max(verified_medical_expiries)
        return f"Verified medical certification expired on {expiry.isoformat()}"

    has_verified_medical = any(
        is_usable_verified(cert) and is_medical_cert_type(cert.cert_type)
        for cert in certifications
    )
    if (
        crew.medical_expiry is not None
        and crew.medical_expiry < start_date
        and not has_verified_medical
    ):
        return f"Medical certification expired on {crew.medical_expiry.isoformat()}"

    expired_survival = [
        cert
        for cert in certifications
        if cert.expiry_date
        and cert.expiry_date < start_date
        and is_usable_verified(cert)
        and any(
            keyword in (cert.cert_type or "").lower()
            for keyword in ("bosiet", "foet", "survival", "opito", "ca-ebs")
        )
    ]
    if expired_survival:
        expiry = max(
            (cert.expiry_date for cert in expired_survival if cert.expiry_date),
            default=start_date,
        )
        return f"Survival certification expired on {expiry.isoformat()}"
    return None


class AssignmentService:
    """Application service for consultant vessel campaign assignments."""

    async def create_assignment(
        self,
        *,
        crew_member_id: str,
        vessel_imo: str,
        role_on_board: str,
        start_date: date,
        end_date: date,
        project_id: Optional[str] = None,
        agreed_day_rate: Optional[float] = None,
        notes: Optional[str] = None,
        status: str = "proposed",
        vessel_name: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> CampaignAssignment:
        """Create a new vessel assignment with compliance & conflict checks."""
        start_date, end_date = _validate_assignment_dates(start_date, end_date)
        clean_role, clean_vessel_name, clean_notes = _normalize_assignment_text(
            role_on_board, vessel_name, notes
        )
        if not isinstance(status, str) or status not in ASSIGNMENT_STATUSES:
            raise ValueError("Invalid assignment status")
        if agreed_day_rate is not None and (
            not isinstance(agreed_day_rate, (int, float))
            or isinstance(agreed_day_rate, bool)
            or not math.isfinite(agreed_day_rate)
            or agreed_day_rate < 0
        ):
            raise ValueError("agreed_day_rate must be a finite non-negative amount")
        clean_imo = _normalize_vessel_imo(vessel_imo)

        factory = get_session_factory()
        async with factory() as session:
            # 1. Verify crew member exists and load profile
            crew_stmt = select(CrewMember).where(CrewMember.id == crew_member_id).with_for_update()
            crew_res = await session.execute(crew_stmt)
            crew = crew_res.scalar_one_or_none()
            if not crew:
                raise ValueError(f"Crew member {crew_member_id} not found")
            if not is_contractor_profile(crew):
                raise ValueError("Crew member is not a contractor profile")
            if (
                actor_role is not None
                and actor_role != "admin"
                and not (
                    crew.publication_status == "approved"
                    or (crew.publication_status == "draft" and crew.submitted_by == actor_id)
                )
            ):
                raise PermissionError("Crew member is not accessible to this actor")

            if status in ACTIVE_ASSIGNMENT_STATUSES:
                cert_res = await session.execute(
                    select(Certification).where(Certification.crew_member_id == crew_member_id)
                )
                credential_issue = _critical_credential_issue(
                    crew, list(cert_res.scalars().all()), start_date
                )
                if credential_issue is not None:
                    raise ValueError(
                        f"Cannot confirm assignment: {credential_issue}. Resolve the credential first."
                    )

            # 2. Schedule conflict check for confirmed/on_board assignments
            if status in ACTIVE_ASSIGNMENT_STATUSES:
                conflict_stmt = select(CampaignAssignment).where(
                    and_(
                        CampaignAssignment.crew_member_id == crew_member_id,
                        CampaignAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                        CampaignAssignment.start_date <= end_date,
                        CampaignAssignment.end_date >= start_date,
                    )
                )
                conflict_res = await session.execute(conflict_stmt)
                if conflict_res.scalar_one_or_none() is not None:
                    raise ValueError(
                        f"Specialist {crew.full_name} already has an active assignment overlapping {start_date} to {end_date}"
                    )

            # 3. Ensure Vessel exists locally in PostgreSQL
            vessel_stmt = select(Vessel).where(Vessel.imo == clean_imo)
            vessel_res = await session.execute(vessel_stmt)
            vessel = vessel_res.scalar_one_or_none()
            if not vessel:
                resolved_name = clean_vessel_name
                if not resolved_name:
                    try:
                        from app.services.vessel_api import vessel_api_service

                        if vessel_api_service.is_configured():
                            summary = await vessel_api_service.get_vessel(clean_imo, id_type="imo")
                            if summary.name:
                                resolved_name = summary.name
                    except Exception as exc:
                        logger.debug(
                            "Could not resolve vessel metadata upstream: %s",
                            type(exc).__name__,
                        )

                vessel = Vessel(
                    imo=clean_imo,
                    name=resolved_name or f"Vessel {clean_imo}",
                )
                session.add(vessel)
                await session.flush()

            # 4. Optional Project validation
            if project_id:
                proj_stmt = select(Project).where(Project.id == project_id)
                proj_res = await session.execute(proj_stmt)
                if proj_res.scalar_one_or_none() is None:
                    raise ValueError(f"Project {project_id} not found")

            # 5. Create CampaignAssignment
            assignment = CampaignAssignment(
                id=str(uuid.uuid4()),
                crew_member_id=crew_member_id,
                project_id=project_id,
                vessel_imo=clean_imo,
                role_on_board=clean_role,
                start_date=start_date,
                end_date=end_date,
                status=status,
                agreed_day_rate=agreed_day_rate,
                notes=clean_notes,
            )
            session.add(assignment)

            # 6. Synchronize CrewMember availability
            if status in ACTIVE_ASSIGNMENT_STATUSES:
                active_stmt = select(CampaignAssignment.end_date).where(
                    and_(
                        CampaignAssignment.crew_member_id == crew.id,
                        CampaignAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                    )
                )
                active_res = await session.execute(active_stmt)
                active_end_dates = list(active_res.scalars().all())
                crew.availability_status = "on_assignment"
                crew.availability_date = max(active_end_dates)

            await session.commit()
            reloaded_stmt = (
                select(CampaignAssignment)
                .options(*_assignment_query_options())
                .where(CampaignAssignment.id == assignment.id)
            )
            reloaded_res = await session.execute(reloaded_stmt)
            result = reloaded_res.scalar_one()

        try:
            await cache_service.delete(cache_service._make_key("summary", crew_member_id))
        except Exception as exc:
            logger.warning("Could not invalidate assignment summary cache (%s)", type(exc).__name__)
        try:
            if not await consultant_knowledge_service.index_crew_member(crew):
                raise RuntimeError("crew indexing was not confirmed")
        except Exception as exc:
            logger.warning("Could not index assignment update (%s)", type(exc).__name__)
            from app.tasks.document_tasks import queue_crew_projection_reconcile

            queue_crew_projection_reconcile(crew_member_id)
        return result

    async def get_assignment(self, assignment_id: str) -> Optional[CampaignAssignment]:
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(CampaignAssignment)
                .options(*_assignment_query_options())
                .where(CampaignAssignment.id == assignment_id)
            )
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def list_assignments(
        self,
        *,
        vessel_imo: Optional[str] = None,
        project_id: Optional[str] = None,
        crew_member_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        actor_id: Optional[str] = None,
        actor_role: str = "user",
    ) -> list[CampaignAssignment]:
        if vessel_imo is not None and not isinstance(vessel_imo, str):
            raise ValueError("vessel_imo must be a string")
        clean_imo = _normalize_vessel_imo(vessel_imo) if vessel_imo is not None else None
        limit, offset = validate_pagination(limit, offset)
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(CampaignAssignment)
                .join(CrewMember, CampaignAssignment.crew_member_id == CrewMember.id)
                .where(
                    CrewMember.password_hash.is_(None),
                    or_(CrewMember.role.is_(None), CrewMember.role.not_in(("staff", "admin"))),
                )
                .options(*_assignment_query_options())
            )
            if actor_role != "admin" and not actor_id:
                return []
            if actor_role != "admin":
                # Staff may inspect approved contractor operations globally,
                # but unpublished draft assignments only for their own drafts.
                stmt = stmt.where(
                    or_(
                        CrewMember.publication_status == "approved",
                        and_(
                            CrewMember.publication_status == "draft",
                            CrewMember.submitted_by == actor_id,
                        ),
                    )
                )
            if clean_imo is not None:
                stmt = stmt.where(CampaignAssignment.vessel_imo == clean_imo)
            if project_id:
                stmt = stmt.where(CampaignAssignment.project_id == project_id)
            if crew_member_id:
                stmt = stmt.where(CampaignAssignment.crew_member_id == crew_member_id)
            if status:
                stmt = stmt.where(CampaignAssignment.status == status)
            stmt = (
                stmt.order_by(CampaignAssignment.start_date.desc(), CampaignAssignment.id.desc())
                .limit(limit)
                .offset(offset)
            )
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def update_status(
        self,
        assignment_id: str,
        new_status: str,
        *,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> CampaignAssignment:
        if not isinstance(new_status, str) or new_status not in ASSIGNMENT_STATUSES:
            raise ValueError(
                f"Invalid assignment status {new_status}; expected one of {sorted(ASSIGNMENT_STATUSES)}"
            )

        factory = get_session_factory()
        async with factory() as session:
            # Read the owner ID before taking a lock, then acquire the
            # contractor lock before the assignment lock. Creation already
            # uses contractor -> assignment conflict locking; keeping the
            # same order prevents PostgreSQL deadlocks during concurrent
            # creation and status transitions.
            lookup = await session.execute(
                select(CampaignAssignment).where(CampaignAssignment.id == assignment_id)
            )
            assignment = lookup.scalar_one_or_none()
            if not assignment:
                raise ValueError(f"Campaign assignment {assignment_id} not found")

            # Serialize every status transition for this contractor before
            # checking overlaps. Without this lock, two proposed assignments
            # can both observe no active peer and become active concurrently.
            crew_stmt = (
                select(CrewMember)
                .where(CrewMember.id == assignment.crew_member_id)
                .with_for_update()
            )
            crew_res = await session.execute(crew_stmt)
            crew = crew_res.scalar_one_or_none()
            if crew is None:
                raise ValueError(f"Crew member {assignment.crew_member_id} not found")

            locked_assignment = await session.execute(
                select(CampaignAssignment)
                .where(CampaignAssignment.id == assignment_id)
                .with_for_update()
            )
            assignment = locked_assignment.scalar_one_or_none()
            if assignment is None:
                raise ValueError(f"Campaign assignment {assignment_id} not found")
            if not is_contractor_profile(crew):
                raise ValueError("Crew member is not a contractor profile")
            if (
                actor_role is not None
                and actor_role != "admin"
                and not (
                    crew.publication_status == "approved"
                    or (crew.publication_status == "draft" and crew.submitted_by == actor_id)
                )
            ):
                raise PermissionError("Crew member is not accessible to this actor")

            if new_status in ACTIVE_ASSIGNMENT_STATUSES:
                cert_res = await session.execute(
                    select(Certification).where(
                        Certification.crew_member_id == assignment.crew_member_id
                    )
                )
                credential_issue = _critical_credential_issue(
                    crew, list(cert_res.scalars().all()), assignment.start_date
                )
                if credential_issue is not None:
                    raise ValueError(
                        f"Cannot confirm assignment: {credential_issue}. Resolve the credential first."
                    )

                overlap_stmt = select(CampaignAssignment).where(
                    and_(
                        CampaignAssignment.crew_member_id == assignment.crew_member_id,
                        CampaignAssignment.id != assignment.id,
                        CampaignAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                        CampaignAssignment.start_date <= assignment.end_date,
                        CampaignAssignment.end_date >= assignment.start_date,
                    )
                )
                overlap_res = await session.execute(overlap_stmt)
                if overlap_res.scalar_one_or_none() is not None:
                    raise ValueError(
                        "Specialist already has an active assignment overlapping "
                        f"{assignment.start_date} to {assignment.end_date}"
                    )

            assignment.status = new_status

            # Re-sync crew availability
            if new_status in ACTIVE_ASSIGNMENT_STATUSES:
                active_stmt = select(CampaignAssignment.end_date).where(
                    and_(
                        CampaignAssignment.crew_member_id == crew.id,
                        CampaignAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                    )
                )
                active_res = await session.execute(active_stmt)
                active_end_dates = list(active_res.scalars().all())
                crew.availability_status = "on_assignment"
                crew.availability_date = max(active_end_dates)
            else:
                # Any transition out of an active status, including a
                # reversion to proposed, must recalculate availability.
                other_stmt = select(CampaignAssignment).where(
                    and_(
                        CampaignAssignment.crew_member_id == crew.id,
                        CampaignAssignment.id != assignment.id,
                        CampaignAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                    )
                )
                other_res = await session.execute(other_stmt)
                remaining = list(other_res.scalars().all())
                if not remaining:
                    crew.availability_status = "available"
                    crew.availability_date = None
                else:
                    crew.availability_status = "on_assignment"
                    crew.availability_date = max(a.end_date for a in remaining)

            await session.commit()
            reloaded_stmt = (
                select(CampaignAssignment)
                .options(*_assignment_query_options())
                .where(CampaignAssignment.id == assignment_id)
            )
            reloaded_res = await session.execute(reloaded_stmt)
            result = reloaded_res.scalar_one()

        try:
            await cache_service.delete(
                cache_service._make_key("summary", assignment.crew_member_id)
            )
        except Exception as exc:
            logger.warning("Could not invalidate assignment summary cache (%s)", type(exc).__name__)
        try:
            if not await consultant_knowledge_service.index_crew_member(crew):
                raise RuntimeError("crew indexing was not confirmed")
        except Exception as exc:
            logger.warning("Could not index assignment status update (%s)", type(exc).__name__)
            from app.tasks.document_tasks import queue_crew_projection_reconcile

            queue_crew_projection_reconcile(assignment.crew_member_id)
        return result

    async def get_vessel(self, imo: str) -> Optional[Vessel]:
        clean_imo = _normalize_vessel_imo(imo)
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Vessel).where(Vessel.imo == clean_imo)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def evaluate_compliance(
        self,
        *,
        crew_member_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Evaluate candidate pre-flight compliance for a campaign window."""
        start_date, end_date = _validate_assignment_dates(start_date, end_date)

        from app.models import Certification

        factory = get_session_factory()
        async with factory() as session:
            crew_stmt = select(CrewMember).where(CrewMember.id == crew_member_id)
            crew_res = await session.execute(crew_stmt)
            crew = crew_res.scalar_one_or_none()
            if not crew:
                raise ValueError(f"Crew member {crew_member_id} not found")
            if not is_contractor_profile(crew):
                raise ValueError("Crew member is not a contractor profile")

            cert_stmt = select(Certification).where(Certification.crew_member_id == crew_member_id)
            cert_res = await session.execute(cert_stmt)
            certs = list(cert_res.scalars().all())

            conflict_stmt = select(CampaignAssignment).where(
                and_(
                    CampaignAssignment.crew_member_id == crew_member_id,
                    CampaignAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                    CampaignAssignment.start_date <= end_date,
                    CampaignAssignment.end_date >= start_date,
                )
            )
            conflict_res = await session.execute(conflict_stmt)
            conflicts = list(conflict_res.scalars().all())

            issues: list[str] = []
            checks: list[dict[str, Any]] = []

            # Check 1: Schedule Conflicts
            if conflicts:
                overlap_desc = ", ".join(
                    f"IMO {a.vessel_imo} ({a.start_date} to {a.end_date})" for a in conflicts
                )
                issues.append(
                    f"Schedule conflict: specialist has active assignment on {overlap_desc}"
                )
                checks.append(
                    {
                        "item": "Schedule Conflict",
                        "status": "fail",
                        "detail": f"Active assignment overlaps: {overlap_desc}",
                    }
                )
            else:
                checks.append(
                    {
                        "item": "Schedule Conflict",
                        "status": "pass",
                        "detail": "No overlapping vessel assignments",
                    }
                )

            # Check 2: Offshore Medical Expiry
            med_expiry = crew.medical_expiry
            med_name = "Offshore Medical"
            med_certs = [
                c
                for c in certs
                if is_medical_cert_type(c.cert_type)
            ]
            if med_certs:
                dated_meds = [
                    c
                    for c in med_certs
                    if c.expiry_date
                    and c.verification_status == "verified"
                    and c.status != "rejected"
                ]
                if dated_meds:
                    best_med = max(dated_meds, key=lambda c: c.expiry_date or date.min)
                    # Verified certificate evidence is authoritative. Do not
                    # let a stale denormalized profile expiry extend a
                    # mobilization beyond the latest verified certificate.
                    med_expiry = best_med.expiry_date
                    med_name = best_med.cert_type
                elif any(
                    c.verification_status == "verified" and c.status != "rejected"
                    for c in med_certs
                ):
                    # Once verified certificate evidence exists, a missing
                    # certificate expiry must not fall back to an older root
                    # profile projection and falsely establish deployability.
                    med_expiry = None
                    med_name = next(
                        c.cert_type
                        for c in med_certs
                        if c.verification_status == "verified" and c.status != "rejected"
                    )

            if not med_expiry:
                if med_certs and any(
                    c.verification_status == "verified" and c.status != "rejected"
                    for c in med_certs
                ):
                    # Verified on file but no expiry anywhere: validity through
                    # the campaign cannot be established — warn, don't pass.
                    issues.append(f"{med_name} verified on file but expiry not recorded")
                    checks.append(
                        {
                            "item": "Offshore Medical",
                            "status": "warn",
                            "detail": f"{med_name} verified on file, expiry not recorded",
                        }
                    )
                else:
                    issues.append("No offshore medical certificate expiry on record")
                    checks.append(
                        {
                            "item": "Offshore Medical",
                            "status": "warn",
                            "detail": "Medical expiry date missing or not verified",
                        }
                    )
            elif med_expiry < start_date:
                issues.append(f"Medical expired on {med_expiry.isoformat()} prior to mobilization")
                checks.append(
                    {
                        "item": "Offshore Medical",
                        "status": "fail",
                        "detail": f"Expired {med_expiry.isoformat()}",
                    }
                )
            elif med_expiry <= end_date:
                issues.append(f"Medical expires during campaign on {med_expiry.isoformat()}")
                checks.append(
                    {
                        "item": "Offshore Medical",
                        "status": "warn",
                        "detail": f"Expires during campaign on {med_expiry.isoformat()}",
                    }
                )
            else:
                checks.append(
                    {
                        "item": "Offshore Medical",
                        "status": "pass",
                        "detail": f"Valid through {med_expiry.isoformat()}",
                    }
                )

            # Check 3: Offshore Survival (BOSIET / FOET)
            survival_certs = [
                c
                for c in certs
                if any(
                    k in (c.cert_type or "").lower()
                    for k in ("bosiet", "foet", "survival", "opito", "ca-ebs")
                )
                and c.status != "rejected"
            ]
            if not survival_certs:
                issues.append("No BOSIET/FOET offshore survival certificate recorded")
                checks.append(
                    {
                        "item": "Survival / BOSIET",
                        "status": "warn",
                        "detail": "No OPITO survival certificate found in records",
                    }
                )
            else:
                valid_survival = [
                    c
                    for c in survival_certs
                    if (
                        c.verification_status == "verified"
                        and c.status != "rejected"
                        and c.expiry_date
                        and c.expiry_date >= end_date
                    )
                ]
                expiring_survival = [
                    c
                    for c in survival_certs
                    if (
                        c.verification_status == "verified"
                        and c.status != "rejected"
                        and c.expiry_date
                        and start_date <= c.expiry_date < end_date
                    )
                ]
                expired_survival = [
                    c
                    for c in survival_certs
                    if (
                        c.verification_status == "verified"
                        and c.status != "rejected"
                        and c.expiry_date
                        and c.expiry_date < start_date
                    )
                ]

                if valid_survival:
                    best = max(valid_survival, key=lambda c: c.expiry_date or date.min)
                    best_expiry = best.expiry_date.isoformat() if best.expiry_date else "valid"
                    checks.append(
                        {
                            "item": "Survival / BOSIET",
                            "status": "pass",
                            "detail": f"{best.cert_type} valid through {best_expiry}",
                        }
                    )
                elif expiring_survival:
                    exp_date = (
                        expiring_survival[0].expiry_date.isoformat()
                        if expiring_survival[0].expiry_date
                        else "soon"
                    )
                    issues.append(
                        f"Survival certificate {expiring_survival[0].cert_type} expires during campaign on {exp_date}"
                    )
                    checks.append(
                        {
                            "item": "Survival / BOSIET",
                            "status": "warn",
                            "detail": f"Expires during campaign on {exp_date}",
                        }
                    )
                elif expired_survival:
                    exp_date = (
                        expired_survival[0].expiry_date.isoformat()
                        if expired_survival[0].expiry_date
                        else "past"
                    )
                    issues.append(
                        f"Survival certificate {expired_survival[0].cert_type} expired on {exp_date}"
                    )
                    checks.append(
                        {
                            "item": "Survival / BOSIET",
                            "status": "fail",
                            "detail": f"Expired on {exp_date}",
                        }
                    )
                elif any(c.verification_status == "verified" for c in survival_certs):
                    issues.append(
                        f"Survival certificate {survival_certs[0].cert_type} verified "
                        "on file but expiry not recorded"
                    )
                    checks.append(
                        {
                            "item": "Survival / BOSIET",
                            "status": "warn",
                            "detail": (
                                f"{survival_certs[0].cert_type} verified on file, "
                                "expiry not recorded"
                            ),
                        }
                    )
                else:
                    checks.append(
                        {
                            "item": "Survival / BOSIET",
                            "status": "warn",
                            "detail": "Survival certificate recorded with open expiry",
                        }
                    )

            if any(c["status"] == "fail" for c in checks):
                verdict = "critical"
            elif any(c["status"] == "warn" for c in checks):
                verdict = "warning"
            else:
                verdict = "compliant"

            return {
                "crew_member_id": crew_member_id,
                "crew_name": crew.full_name,
                "status": verdict,
                "has_conflict": len(conflicts) > 0,
                "issues": issues,
                "checks": checks,
            }


assignment_service = AssignmentService()
