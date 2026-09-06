"""Campaign assignment service — manages consultant deployment to vessels and projects."""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.database import get_session_factory
from app.models import CampaignAssignment, CrewMember, Project, Vessel

logger = logging.getLogger(__name__)

ACTIVE_ASSIGNMENT_STATUSES = {"confirmed", "on_board"}


def _assignment_query_options() -> tuple[Any, ...]:
    """Eagerly load related models to prevent async greenlet lazy-load errors outside session."""
    return (
        selectinload(CampaignAssignment.crew_member),
        selectinload(CampaignAssignment.vessel),
        selectinload(CampaignAssignment.project),
    )


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
    ) -> CampaignAssignment:
        """Create a new vessel assignment with compliance & conflict checks."""
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        if not role_on_board.strip():
            raise ValueError("role_on_board must not be empty")

        factory = get_session_factory()
        async with factory() as session:
            # 1. Verify crew member exists and load profile
            crew_stmt = select(CrewMember).where(CrewMember.id == crew_member_id)
            crew_res = await session.execute(crew_stmt)
            crew = crew_res.scalar_one_or_none()
            if not crew:
                raise ValueError(f"Crew member {crew_member_id} not found")

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
            clean_imo = vessel_imo.strip()
            vessel_stmt = select(Vessel).where(Vessel.imo == clean_imo)
            vessel_res = await session.execute(vessel_stmt)
            vessel = vessel_res.scalar_one_or_none()
            if not vessel:
                resolved_name = vessel_name.strip() if vessel_name and vessel_name.strip() else None
                if not resolved_name:
                    try:
                        from app.services.vessel_api import vessel_api_service

                        if vessel_api_service.is_configured():
                            summary = await vessel_api_service.get_vessel(clean_imo, id_type="imo")
                            if summary.name:
                                resolved_name = summary.name
                    except Exception as exc:
                        logger.debug("Could not resolve vessel metadata upstream: %s", exc)

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
                role_on_board=role_on_board.strip(),
                start_date=start_date,
                end_date=end_date,
                status=status,
                agreed_day_rate=agreed_day_rate,
                notes=notes,
            )
            session.add(assignment)

            # 6. Synchronize CrewMember availability
            if status in ACTIVE_ASSIGNMENT_STATUSES:
                crew.availability_status = "on_assignment"
                crew.availability_date = end_date

            await session.commit()
            reloaded_stmt = (
                select(CampaignAssignment)
                .options(*_assignment_query_options())
                .where(CampaignAssignment.id == assignment.id)
            )
            reloaded_res = await session.execute(reloaded_stmt)
            return reloaded_res.scalar_one()

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
    ) -> list[CampaignAssignment]:
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CampaignAssignment).options(*_assignment_query_options())
            if vessel_imo:
                stmt = stmt.where(CampaignAssignment.vessel_imo == vessel_imo.strip())
            if project_id:
                stmt = stmt.where(CampaignAssignment.project_id == project_id)
            if crew_member_id:
                stmt = stmt.where(CampaignAssignment.crew_member_id == crew_member_id)
            if status:
                stmt = stmt.where(CampaignAssignment.status == status)
            stmt = stmt.order_by(CampaignAssignment.start_date.desc())
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def update_status(self, assignment_id: str, new_status: str) -> CampaignAssignment:
        valid_statuses = {"proposed", "confirmed", "on_board", "completed", "cancelled"}
        if new_status not in valid_statuses:
            raise ValueError(
                f"Invalid assignment status {new_status}; expected one of {sorted(valid_statuses)}"
            )

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CampaignAssignment).where(CampaignAssignment.id == assignment_id)
            res = await session.execute(stmt)
            assignment = res.scalar_one_or_none()
            if not assignment:
                raise ValueError(f"Campaign assignment {assignment_id} not found")

            assignment.status = new_status

            # Re-sync crew availability
            crew_stmt = select(CrewMember).where(CrewMember.id == assignment.crew_member_id)
            crew_res = await session.execute(crew_stmt)
            crew = crew_res.scalar_one_or_none()
            if crew:
                if new_status in ACTIVE_ASSIGNMENT_STATUSES:
                    crew.availability_status = "on_assignment"
                    crew.availability_date = assignment.end_date
                elif new_status in ("completed", "cancelled"):
                    # Check if crew has any other active assignments
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
            return reloaded_res.scalar_one()

    async def get_vessel(self, imo: str) -> Optional[Vessel]:
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Vessel).where(Vessel.imo == imo.strip())
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
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")

        from app.models import Certification

        factory = get_session_factory()
        async with factory() as session:
            crew_stmt = select(CrewMember).where(CrewMember.id == crew_member_id)
            crew_res = await session.execute(crew_stmt)
            crew = crew_res.scalar_one_or_none()
            if not crew:
                raise ValueError(f"Crew member {crew_member_id} not found")

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
                if any(k in (c.cert_type or "").lower() for k in ("medical", "oguk", "oeuk"))
            ]
            if med_certs:
                dated_meds = [c for c in med_certs if c.expiry_date]
                if dated_meds:
                    best_med = max(dated_meds, key=lambda c: c.expiry_date or date.min)
                    if not med_expiry or (
                        best_med.expiry_date and best_med.expiry_date > med_expiry
                    ):
                        med_expiry = best_med.expiry_date
                        med_name = best_med.cert_type
                elif not med_expiry and any(
                    c.status == "valid" or c.verification_status == "verified" for c in med_certs
                ):
                    med_name = med_certs[0].cert_type

            if not med_expiry:
                if med_certs and any(
                    c.status == "valid" or c.verification_status == "verified" for c in med_certs
                ):
                    checks.append(
                        {
                            "item": "Offshore Medical",
                            "status": "pass",
                            "detail": f"{med_name} verified on file",
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
                    c for c in survival_certs if c.expiry_date and c.expiry_date >= end_date
                ]
                expiring_survival = [
                    c
                    for c in survival_certs
                    if c.expiry_date and start_date <= c.expiry_date < end_date
                ]
                expired_survival = [
                    c for c in survival_certs if c.expiry_date and c.expiry_date < start_date
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
                elif any(
                    c.status == "valid" or c.verification_status == "verified"
                    for c in survival_certs
                ):
                    checks.append(
                        {
                            "item": "Survival / BOSIET",
                            "status": "pass",
                            "detail": f"{survival_certs[0].cert_type} verified on file",
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
