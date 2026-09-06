"""Unit and integration tests for consultant campaign vessel assignments."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import CrewMember, Project, Vessel
from app.services.assignment import assignment_service


async def _create_test_crew(db_session: Any, name: str = "Morgan Reed", availability: str = "available") -> CrewMember:
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        availability_status=availability,
        role="user",
    )
    db_session.add(crew)
    await db_session.commit()
    await db_session.refresh(crew)
    return crew


async def _create_test_project(db_session: Any, name: str = "Beryl Wind Farm") -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        client_name="Equinor",
        project_name=name,
        project_type="offshore_wind",
        location="North Sea",
        status="active",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.mark.asyncio
async def test_create_assignment_persists_vessel_and_assignment(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Sarah Connor")
    proj = await _create_test_project(db_session, "Forties Survey")

    start = date(2026, 10, 1)
    end = date(2026, 10, 21)

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        assignment = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9683934",
            vessel_name="Fugro Pioneer",
            role_on_board="Senior Hydrographer",
            start_date=start,
            end_date=end,
            project_id=proj.id,
            status="confirmed",
            agreed_day_rate=850.0,
        )

        assert assignment.id is not None
        assert assignment.vessel_imo == "9683934"
        assert assignment.role_on_board == "Senior Hydrographer"
        assert assignment.status == "confirmed"

        # Verify vessel was upserted in DB
        vessel_stmt = select(Vessel).where(Vessel.imo == "9683934")
        vessel_res = await db_session.execute(vessel_stmt)
        vessel = vessel_res.scalar_one_or_none()
        assert vessel is not None
        assert vessel.name == "Fugro Pioneer"

        # Verify crew availability synchronized to on_assignment
        crew_row = (await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))).scalar_one()
        assert crew_row.availability_status == "on_assignment"
        assert crew_row.availability_date == end


@pytest.mark.asyncio
async def test_create_assignment_schedule_conflict_rejected(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "David Bowman")

    start1 = date(2026, 11, 1)
    end1 = date(2026, 11, 20)

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9683934",
            vessel_name="Fugro Pioneer",
            role_on_board="Party Chief",
            start_date=start1,
            end_date=end1,
            status="confirmed",
        )

        # Attempt overlapping assignment
        start2 = date(2026, 11, 10)
        end2 = date(2026, 11, 30)
        with pytest.raises(ValueError, match="already has an active assignment overlapping"):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo="9700000",
                vessel_name="Ocean Pride",
                role_on_board="Client Rep",
                start_date=start2,
                end_date=end2,
                status="confirmed",
            )


@pytest.mark.asyncio
async def test_update_status_resets_availability(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Ellen Ripley")

    start = date(2026, 12, 1)
    end = date(2026, 12, 15)

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        assignment = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9683934",
            role_on_board="Survey Engineer",
            start_date=start,
            end_date=end,
            status="confirmed",
        )
        crew_row = (await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))).scalar_one()
        assert crew_row.availability_status == "on_assignment"

        # Complete assignment
        updated = await assignment_service.update_status(assignment.id, "completed")
        assert updated.status == "completed"

        crew_row_done = (await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))).scalar_one()
        assert crew_row_done.availability_status == "available"
        assert crew_row_done.availability_date is None


@pytest.mark.asyncio
async def test_date_and_role_validation(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Arthur Dent")

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        # End date before start date
        with pytest.raises(ValueError, match="start_date must be on or before end_date"):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo="9683934",
                role_on_board="Observer",
                start_date=date(2026, 10, 20),
                end_date=date(2026, 10, 10),
            )

        # Empty role
        with pytest.raises(ValueError, match="role_on_board must not be empty"):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo="9683934",
                role_on_board="   ",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 10),
            )


@pytest.mark.asyncio
async def test_list_and_roster(db_session: Any) -> None:
    crew1 = await _create_test_crew(db_session, "Specialist One")
    crew2 = await _create_test_crew(db_session, "Specialist Two")

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        await assignment_service.create_assignment(
            crew_member_id=crew1.id,
            vessel_imo="9111111",
            role_on_board="Role A",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 15),
            status="confirmed",
        )
        await assignment_service.create_assignment(
            crew_member_id=crew2.id,
            vessel_imo="9111111",
            role_on_board="Role B",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 15),
            status="confirmed",
        )

        roster = await assignment_service.list_assignments(vessel_imo="9111111")
        assert len(roster) == 2
        assigned_crew_ids = {a.crew_member_id for a in roster}
        assert crew1.id in assigned_crew_ids
        assert crew2.id in assigned_crew_ids


@pytest.mark.asyncio
async def test_evaluate_compliance(db_session: Any) -> None:
    from app.models import Certification

    crew = await _create_test_crew(db_session, "Gillian Anderson")
    crew.medical_expiry = date(2026, 12, 31)

    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OPITO BOSIET with CA-EBS",
        expiry_date=date(2027, 5, 1),
        status="valid",
    )
    db_session.add(cert)
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        # 1. Fully compliant case
        report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 28),
        )
        assert report["status"] == "compliant"
        assert report["has_conflict"] is False
        assert len(report["issues"]) == 0

        # 2. Conflicting assignment created
        await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9222222",
            role_on_board="PAM Operator",
            start_date=date(2026, 10, 10),
            end_date=date(2026, 10, 25),
            status="confirmed",
        )

        conflict_report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 28),
        )
        assert conflict_report["status"] == "critical"
        assert conflict_report["has_conflict"] is True
        assert any("Schedule conflict" in issue for issue in conflict_report["issues"])


@pytest.mark.asyncio
async def test_evaluate_assignment_compliance_graphql(client: Any, db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Dana Scully")
    crew.medical_expiry = date(2026, 12, 31)

    query = """
        query EvaluateCompliance($crewId: String!, $startDate: String!, $endDate: String!) {
            evaluateAssignmentCompliance(crewMemberId: $crewId, startDate: $startDate, endDate: $endDate) {
                crewMemberId
                crewName
                status
                hasConflict
                issues
                checks {
                    item
                    status
                    detail
                }
            }
        }
    """

    res = await client.post(
        "/graphql",
        json={
            "query": query,
            "variables": {
                "crewId": crew.id,
                "startDate": "2026-10-01",
                "endDate": "2026-10-28",
            },
        },
    )

    body = res.json()
    assert "errors" not in body, body
    data = body["data"]["evaluateAssignmentCompliance"]
    assert data["crewMemberId"] == crew.id
    assert data["crewName"] == "Dana Scully"
    assert data["status"] in ("compliant", "warning", "critical")
    assert isinstance(data["checks"], list)


@pytest.mark.asyncio
async def test_multi_assignment_lifecycle_and_remaining_date(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Fox Mulder")

    start1 = date(2026, 10, 1)
    end1 = date(2026, 10, 15)
    start2 = date(2026, 11, 1)
    end2 = date(2026, 11, 20)

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        # 1. Create first assignment
        a1 = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9111111",
            role_on_board="QC 1",
            start_date=start1,
            end_date=end1,
            status="confirmed",
        )
        # 2. Create second non-overlapping assignment
        a2 = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9222222",
            role_on_board="QC 2",
            start_date=start2,
            end_date=end2,
            status="confirmed",
        )

        # Complete first assignment — should NOT set available, should preserve end date of a2
        await assignment_service.update_status(a1.id, "completed")
        c_row = (await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))).scalar_one()
        assert c_row.availability_status == "on_assignment"
        assert c_row.availability_date == end2

        # Complete second assignment — now should be available
        await assignment_service.update_status(a2.id, "completed")
        c_row_done = (await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))).scalar_one()
        assert c_row_done.availability_status == "available"
        assert c_row_done.availability_date is None


@pytest.mark.asyncio
async def test_schedule_conflict_exact_boundaries(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Walter Skinner")

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        # Active assignment Oct 1 to Oct 15
        await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9111111",
            role_on_board="Rep",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 15),
            status="confirmed",
        )

        # Boundary touch: Oct 15 to Oct 25 should conflict
        with pytest.raises(ValueError, match="already has an active assignment overlapping"):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo="9222222",
                role_on_board="Rep",
                start_date=date(2026, 10, 15),
                end_date=date(2026, 10, 25),
                status="confirmed",
            )

        # Adjacent day: Oct 16 to Oct 30 must NOT conflict
        adjacent = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9222222",
            role_on_board="Rep",
            start_date=date(2026, 10, 16),
            end_date=date(2026, 10, 30),
            status="confirmed",
        )
        assert adjacent.id is not None


@pytest.mark.asyncio
async def test_evaluate_compliance_credential_edge_cases(db_session: Any) -> None:
    from app.models import Certification

    crew = await _create_test_crew(db_session, "Luke Skywalker")
    # Stale expired medical on profile
    crew.medical_expiry = date(2024, 1, 1)

    # Renewed valid medical in certs
    valid_med = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OEUK Offshore Medical",
        expiry_date=date(2027, 12, 1),
        status="valid",
    )
    # Expired old BOSIET
    old_bosiet = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="BOSIET",
        expiry_date=date(2023, 6, 1),
        status="expired",
    )
    # Renewed valid FOET
    valid_foet = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OPITO FOET with CA-EBS",
        expiry_date=date(2027, 8, 15),
        status="valid",
    )
    db_session.add_all([valid_med, old_bosiet, valid_foet])
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        # 1. Should be compliant because renewed OEUK and FOET take precedence
        report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 28),
        )
        assert report["status"] == "compliant"
        assert len(report["issues"]) == 0

        # 2. Campaign extending past FOET expiry -> should return warning
        warn_report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2027, 8, 1),
            end_date=date(2027, 8, 30),
        )
        assert warn_report["status"] == "warning"
        assert any("expires during campaign" in issue for issue in warn_report["issues"])

        # 3. Campaign starting after FOET expiry -> should return critical
        fail_report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2027, 9, 1),
            end_date=date(2027, 9, 30),
        )
        assert fail_report["status"] == "critical"
        assert any("expired" in issue.lower() for issue in fail_report["issues"])


@pytest.mark.asyncio
async def test_assignment_inverted_dates_rejected(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Inverted Candidate")
    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        with pytest.raises(ValueError, match="start_date must be on or before end_date"):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo="9111111",
                role_on_board="QC",
                start_date=date(2026, 10, 20),
                end_date=date(2026, 10, 10),
            )


@pytest.mark.asyncio
async def test_assignment_empty_role_rejected(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "No Role Candidate")
    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        with pytest.raises(ValueError, match="role_on_board must not be empty"):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo="9111111",
                role_on_board="   ",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 10),
            )


@pytest.mark.asyncio
async def test_assignment_enclosure_conflict(db_session: Any) -> None:
    """An assignment completely enclosed inside another active assignment must be rejected."""
    crew = await _create_test_crew(db_session, "Enclosure Candidate")
    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        # Outer assignment Oct 1 -> Oct 31
        await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9111111",
            role_on_board="MMO",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            status="confirmed",
        )
        # Inner attempt Oct 10 -> Oct 20
        with pytest.raises(ValueError, match="already has an active assignment overlapping"):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo="9222222",
                role_on_board="MMO",
                start_date=date(2026, 10, 10),
                end_date=date(2026, 10, 20),
                status="confirmed",
            )


@pytest.mark.asyncio
async def test_assignment_envelope_conflict(db_session: Any) -> None:
    """An assignment that envelopes an already scheduled inner assignment must be rejected."""
    crew = await _create_test_crew(db_session, "Envelope Candidate")
    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        # Inner assignment Oct 10 -> Oct 20
        await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9111111",
            role_on_board="Hydrographer",
            start_date=date(2026, 10, 10),
            end_date=date(2026, 10, 20),
            status="confirmed",
        )
        # Outer attempt Oct 1 -> Oct 31
        with pytest.raises(ValueError, match="already has an active assignment overlapping"):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo="9222222",
                role_on_board="Hydrographer",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 31),
                status="confirmed",
            )


@pytest.mark.asyncio
async def test_assignment_cancelled_does_not_block_schedule(db_session: Any) -> None:
    """A cancelled assignment does not block the specialist from being booked during that window."""
    crew = await _create_test_crew(db_session, "Cancelled Candidate")
    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        # 1. Create assignment and cancel it
        a1 = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9111111",
            role_on_board="Client Rep",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 20),
            status="confirmed",
        )
        await assignment_service.update_status(a1.id, "cancelled")

        # 2. Re-book overlapping window should now succeed
        a2 = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9222222",
            role_on_board="Client Rep",
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 15),
            status="confirmed",
        )
        assert a2.id is not None
        assert a2.status == "confirmed"


@pytest.mark.asyncio
async def test_assignment_single_day_mobilization(db_session: Any) -> None:
    """A 1-day mobilization where start_date == end_date is valid."""
    crew = await _create_test_crew(db_session, "Single Day Candidate")
    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        assignment = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9333333",
            role_on_board="Inspector",
            start_date=date(2026, 11, 15),
            end_date=date(2026, 11, 15),
            status="confirmed",
        )
        assert assignment.id is not None
        assert assignment.start_date == assignment.end_date




