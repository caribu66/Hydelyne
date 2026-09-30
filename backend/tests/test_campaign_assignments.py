"""Unit and integration tests for consultant campaign vessel assignments."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Certification, CrewMember, Project, Vessel
from app.services.assignment import (
    MAX_ASSIGNMENT_NOTES_LENGTH,
    MAX_ROLE_ON_BOARD_LENGTH,
    MAX_VESSEL_NAME_LENGTH,
    _critical_credential_issue,
    _normalize_assignment_text,
    _normalize_vessel_imo,
    assignment_service,
)
from app.services.certification_projection import reconcile_medical_profile
from app.services.crew import crew_service


class _AssignmentSessionContext:
    def __init__(self, session: object):
        self.session = session

    async def __aenter__(self) -> object:
        return self.session

    async def __aexit__(self, *_args: object) -> bool:
        return False


class _AssignmentResult:
    def __init__(self, value: object = None, values: list[object] | None = None):
        self.value = value
        self.values = values or []

    def scalar_one_or_none(self) -> object:
        return self.value

    def scalars(self) -> "_AssignmentResult":
        return self

    def all(self) -> list[object]:
        return self.values


def test_normalize_vessel_imo_rejects_blank_and_oversized_keys() -> None:
    assert _normalize_vessel_imo("  9683934  ") == "9683934"
    with pytest.raises(ValueError, match="must not be empty"):
        _normalize_vessel_imo("  ")
    with pytest.raises(ValueError, match="too long"):
        _normalize_vessel_imo("1" * 21)
    with pytest.raises(ValueError, match="invalid characters"):
        _normalize_vessel_imo("9683934/position")


@pytest.mark.asyncio
async def test_assignment_listing_rejects_blank_vessel_filter() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await assignment_service.list_assignments(vessel_imo=" ")


@pytest.mark.asyncio
async def test_status_update_locks_contractor_before_assignment(monkeypatch: pytest.MonkeyPatch) -> None:
    assignment = SimpleNamespace(
        id="assignment-1",
        crew_member_id="crew-1",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 10),
    )
    crew = SimpleNamespace(
        password_hash=None,
        role=None,
        publication_status="approved",
        submitted_by=None,
        medical_expiry=date(2026, 9, 1),
        availability_status="available",
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _AssignmentResult(assignment),
                _AssignmentResult(crew),
                _AssignmentResult(assignment),
                _AssignmentResult(values=[]),
                _AssignmentResult(values=[]),
            ]
        )
    )
    monkeypatch.setattr(
        "app.services.assignment.get_session_factory",
        lambda: lambda: _AssignmentSessionContext(session),
    )

    with pytest.raises(ValueError, match="Cannot confirm assignment"):
        await assignment_service.update_status("assignment-1", "confirmed")

    statements = [call.args[0] for call in session.execute.await_args_list]
    assert "FOR UPDATE" not in str(statements[0])
    assert "FOR UPDATE" in str(statements[1])
    assert "FOR UPDATE" in str(statements[2])


def test_assignment_text_limits_match_database_contract() -> None:
    assert _normalize_assignment_text("  Survey Lead  ", "  Aurora  ", "  note  ") == (
        "Survey Lead",
        "Aurora",
        "note",
    )
    with pytest.raises(ValueError, match="role_on_board"):
        _normalize_assignment_text("x" * (MAX_ROLE_ON_BOARD_LENGTH + 1), None, None)
    with pytest.raises(ValueError, match="vessel_name"):
        _normalize_assignment_text("Role", "x" * (MAX_VESSEL_NAME_LENGTH + 1), None)
    with pytest.raises(ValueError, match="notes"):
        _normalize_assignment_text("Role", None, "x" * (MAX_ASSIGNMENT_NOTES_LENGTH + 1))
    with pytest.raises(ValueError, match="role_on_board"):
        _normalize_assignment_text(42, None, None)


def test_confirmed_assignment_blocks_expired_verified_credentials() -> None:
    crew = CrewMember(full_name="Expired Credential Crew", medical_expiry=date(2026, 9, 1))
    medical = Certification(
        cert_type="OGUK Medical",
        expiry_date=date(2026, 9, 1),
        status="expired",
        verification_status="verified",
    )

    issue = _critical_credential_issue(crew, [medical], date(2026, 10, 1))

    assert issue == "Verified medical certification expired on 2026-09-01"


def test_assignment_uses_expiry_date_when_credential_status_is_stale() -> None:
    crew = CrewMember(full_name="Stale Credential Crew", medical_expiry=date(2027, 1, 1))
    medical = Certification(
        cert_type="OGUK Medical",
        expiry_date=date(2027, 1, 1),
        status="expired",
        verification_status="verified",
    )

    issue = _critical_credential_issue(crew, [medical], date(2026, 10, 1))

    assert issue is None


def test_rejected_credential_cannot_be_used_by_stale_verified_flag() -> None:
    crew = CrewMember(full_name="Rejected Credential Crew")
    medical = Certification(
        cert_type="OGUK Medical",
        expiry_date=date(2026, 9, 1),
        status="rejected",
        verification_status="verified",
    )

    issue = _critical_credential_issue(crew, [medical], date(2026, 10, 1))

    assert issue is None


def test_rejected_profile_cannot_be_confirmed_for_assignment() -> None:
    crew = CrewMember(
        full_name="Rejected Profile Crew",
        publication_status="rejected",
    )

    issue = _critical_credential_issue(crew, [], date(2026, 10, 1))

    assert issue == "Specialist profile is rejected"


def test_confirmed_assignment_blocks_unavailable_crew() -> None:
    crew = CrewMember(full_name="Unavailable Crew", availability_status="unavailable")

    issue = _critical_credential_issue(crew, [], date(2026, 10, 1))

    assert issue == "Specialist is marked unavailable"


def test_confirmed_assignment_blocks_crew_until_release_date() -> None:
    crew = CrewMember(
        full_name="Still Assigned Crew",
        availability_status="on_assignment",
        availability_date=date(2026, 10, 15),
    )

    issue = _critical_credential_issue(crew, [], date(2026, 10, 1))

    assert issue == "Specialist is on assignment through 2026-10-15"


def test_assignment_allows_crew_released_before_start_date() -> None:
    crew = CrewMember(
        full_name="Released Crew",
        availability_status="on_assignment",
        availability_date=date(2026, 9, 30),
    )

    assert _critical_credential_issue(crew, [], date(2026, 10, 1)) is None


async def _create_test_crew(
    db_session: Any, name: str = "Morgan Reed", availability: str = "available"
) -> CrewMember:
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
        crew_row = (
            await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))
        ).scalar_one()
        assert crew_row.availability_status == "on_assignment"
        assert crew_row.availability_date == end


@pytest.mark.asyncio
async def test_create_assignment_rejects_login_accounts(db_session: Any) -> None:
    account = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Operations Account",
        role="staff",
        password_hash="stored-password-hash",
        publication_status="approved",
    )
    db_session.add(account)
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        with pytest.raises(ValueError, match="not a contractor profile"):
            await assignment_service.create_assignment(
                crew_member_id=account.id,
                vessel_imo="9683934",
                role_on_board="Operations Lead",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 10),
                actor_role="admin",
            )


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
async def test_update_status_to_active_rejects_overlap(db_session: Any) -> None:
    """Proposed overlapping bookings must not escalate to active via update_status."""
    crew = await _create_test_crew(db_session, "Frank Poole")

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        active = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9683934",
            role_on_board="Party Chief",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 20),
            status="confirmed",
        )
        assert active.status == "confirmed"

        overlapping = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9700000",
            role_on_board="Client Rep",
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 30),
            status="proposed",
        )
        with pytest.raises(ValueError, match="already has an active assignment overlapping"):
            await assignment_service.update_status(overlapping.id, "confirmed")


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
        crew_row = (
            await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))
        ).scalar_one()
        assert crew_row.availability_status == "on_assignment"

        # Complete assignment
        updated = await assignment_service.update_status(assignment.id, "completed")
        assert updated.status == "completed"

        crew_row_done = (
            await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))
        ).scalar_one()
        assert crew_row_done.availability_status == "available"
        assert crew_row_done.availability_date is None


@pytest.mark.asyncio
async def test_reverting_active_assignment_resets_availability(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Leia Organa")

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        assignment = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9683934",
            role_on_board="Survey Engineer",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 15),
            status="confirmed",
        )
        await assignment_service.update_status(assignment.id, "proposed")

    crew_row = (
        await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))
    ).scalar_one()
    assert crew_row.availability_status == "available"
    assert crew_row.availability_date is None


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

        with pytest.raises(ValueError, match="start_date and end_date must be dates"):
            await assignment_service.evaluate_compliance(
                crew_member_id=crew.id,
                start_date=datetime(2026, 10, 1, 9, 0),
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

        roster = await assignment_service.list_assignments(vessel_imo="9111111", actor_role="admin")
        assert len(roster) == 2
        assigned_crew_ids = {a.crew_member_id for a in roster}
        assert crew1.id in assigned_crew_ids
        assert crew2.id in assigned_crew_ids


@pytest.mark.asyncio
async def test_staff_assignment_listing_scopes_unpublished_drafts(db_session: Any) -> None:
    owner_id = str(uuid.uuid4())
    other_owner_id = str(uuid.uuid4())
    approved = await _create_test_crew(db_session, "Approved Specialist")
    own_draft = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Own Draft",
        publication_status="draft",
        submitted_by=owner_id,
    )
    other_draft = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Other Draft",
        publication_status="draft",
        submitted_by=other_owner_id,
    )
    db_session.add_all([own_draft, other_draft])
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        for crew in (approved, own_draft, other_draft):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo=f"9{len(crew.id)}",
                role_on_board="Role",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 15),
            )

        visible = await assignment_service.list_assignments(
            actor_id=owner_id,
            actor_role="staff",
        )

    visible_ids = {assignment.crew_member_id for assignment in visible}
    assert visible_ids == {approved.id, own_draft.id}


@pytest.mark.asyncio
async def test_missing_actor_id_fails_closed_for_drafts(db_session: Any) -> None:
    draft = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Unowned Draft",
        publication_status="draft",
        submitted_by=None,
    )
    db_session.add(draft)
    await db_session.commit()

    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        assert (
            await crew_service.can_access_profile(
                draft.id,
                actor_id=None,
                actor_role="staff",
            )
            is False
        )


@pytest.mark.asyncio
async def test_assignment_mutations_recheck_draft_access_inside_transaction(
    db_session: Any,
) -> None:
    owner_id = "staff-owner"
    other_id = "staff-other"
    denied_draft = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Denied Draft",
        publication_status="draft",
        submitted_by=other_id,
    )
    allowed_draft = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Allowed Draft",
        publication_status="draft",
        submitted_by=owner_id,
    )
    db_session.add_all([denied_draft, allowed_draft])
    await db_session.commit()

    with pytest.raises(PermissionError):
        await assignment_service.create_assignment(
            crew_member_id=denied_draft.id,
            vessel_imo="9111111",
            role_on_board="Role",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 15),
            actor_id=owner_id,
            actor_role="staff",
        )

    assignment = await assignment_service.create_assignment(
        crew_member_id=allowed_draft.id,
        vessel_imo="9111111",
        role_on_board="Role",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 15),
        actor_id=owner_id,
        actor_role="staff",
    )
    allowed_draft.submitted_by = other_id
    await db_session.commit()
    await db_session.refresh(allowed_draft)
    assert allowed_draft.submitted_by == other_id
    with pytest.raises(PermissionError):
        await assignment_service.update_status(
            assignment.id,
            "confirmed",
            actor_id=owner_id,
            actor_role="staff",
        )


@pytest.mark.asyncio
async def test_missing_actor_id_returns_no_staff_assignments(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Scoped Specialist")

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9222222",
            role_on_board="Role",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 15),
        )
        visible = await assignment_service.list_assignments(
            actor_id=None,
            actor_role="staff",
        )

    assert visible == []


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
        verification_status="verified",
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
        c_row = (
            await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))
        ).scalar_one()
        assert c_row.availability_status == "on_assignment"
        assert c_row.availability_date == end2

        # Complete second assignment — now should be available
        await assignment_service.update_status(a2.id, "completed")
        c_row_done = (
            await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))
        ).scalar_one()
        assert c_row_done.availability_status == "available"
        assert c_row_done.availability_date is None


@pytest.mark.asyncio
async def test_active_assignment_keeps_latest_end_date_when_added_out_of_order(
    db_session: Any,
) -> None:
    """Availability must reflect every active tour, not the latest mutation."""
    crew = await _create_test_crew(db_session, "Jean-Luc Picard")

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        future = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9111111",
            role_on_board="Survey Lead",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 1, 20),
            status="confirmed",
        )
        earlier = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9222222",
            role_on_board="Survey QC",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 15),
            status="proposed",
        )

        await assignment_service.update_status(earlier.id, "confirmed")

    crew_row = (
        await db_session.execute(select(CrewMember).where(CrewMember.id == crew.id))
    ).scalar_one()
    assert future.status == "confirmed"
    assert crew_row.availability_status == "on_assignment"
    assert crew_row.availability_date == date(2027, 1, 20)


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
async def test_evaluate_compliance_verified_no_expiry_warns(db_session: Any) -> None:
    """Verified-on-file certs without any expiry must warn, not pass."""
    from app.models import Certification

    crew = await _create_test_crew(db_session, "Wedge Antilles")
    crew.medical_expiry = date(2030, 1, 1)
    db_session.add_all(
        [
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="OGUK Medical",
                expiry_date=None,
                status="valid",
                verification_status="verified",
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="OPITO BOSIET",
                expiry_date=None,
                status="valid",
                verification_status="verified",
            ),
        ]
    )
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 28),
        )
        assert report["status"] == "warning"
        assert any("OGUK Medical verified on file" in issue for issue in report["issues"])


@pytest.mark.asyncio
async def test_evaluate_compliance_uses_expiring_medical_certificate_date(db_session: Any) -> None:
    """An expiring verified medical must report its real expiry date."""
    from app.models import Certification

    crew = await _create_test_crew(db_session, "Medical Expiry Specialist")
    db_session.add_all(
        [
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="OGUK Medical",
                expiry_date=date(2026, 10, 15),
                status="expiring_soon",
                verification_status="verified",
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="OPITO BOSIET",
                expiry_date=date(2026, 10, 15),
                status="expiring_soon",
                verification_status="verified",
            ),
        ]
    )
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 28),
        )

    assert report["status"] == "warning"
    assert any("expires during campaign" in issue for issue in report["issues"])
    assert not any("expiry not recorded" in issue for issue in report["issues"])
    assert any("Survival certificate" in issue for issue in report["issues"])


@pytest.mark.asyncio
async def test_evaluate_compliance_does_not_trust_stale_profile_medical_expiry(
    db_session: Any,
) -> None:
    """Verified certificate evidence must override a stale profile projection."""
    from app.models import Certification

    crew = await _create_test_crew(db_session, "Stale Medical Projection")
    crew.medical_expiry = date(2030, 1, 1)
    db_session.add(
        Certification(
            id=str(uuid.uuid4()),
            crew_member_id=crew.id,
            cert_type="OGUK Medical",
            expiry_date=date(2026, 10, 15),
            status="valid",
            verification_status="verified",
        )
    )
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 28),
        )

    assert report["status"] == "critical"
    assert any("Medical expired" in issue for issue in report["issues"])


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
        verification_status="verified",
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
        verification_status="verified",
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
async def test_evaluate_compliance_ignores_rejected_future_certificates(db_session: Any) -> None:
    from app.models import Certification

    crew = await _create_test_crew(db_session, "Rejected Credentials")
    crew.medical_expiry = date(2024, 1, 1)
    db_session.add_all(
        [
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="OGUK Medical",
                expiry_date=date(2028, 1, 1),
                status="rejected",
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="BOSIET",
                expiry_date=date(2028, 1, 1),
                status="rejected",
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="FOET",
                expiry_date=date(2025, 1, 1),
                status="rejected",
            ),
        ]
    )
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 28),
        )

    assert report["status"] == "critical"
    assert any("Medical expired" in issue for issue in report["issues"])
    survival_check = next(
        check for check in report["checks"] if check["item"] == "Survival / BOSIET"
    )
    assert survival_check["status"] == "warn"


@pytest.mark.asyncio
async def test_evaluate_compliance_does_not_deploy_pending_medical_certificate(
    db_session: Any,
) -> None:
    """Pending medical evidence must not populate the deployability projection."""
    from app.models import Certification

    crew = await _create_test_crew(db_session, "Pending Medical Evidence")
    pending_medical = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=date(2027, 1, 1),
        status="pending_verification",
        verification_status="unverified",
    )
    db_session.add(pending_medical)
    await db_session.commit()

    await reconcile_medical_profile(db_session, crew_id=crew.id)
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 28),
        )

    assert crew.medical_expiry is None
    assert report["status"] == "warning"
    assert any("No offshore medical certificate expiry" in issue for issue in report["issues"])


@pytest.mark.asyncio
async def test_evaluate_compliance_does_not_deploy_unverified_valid_medical(
    db_session: Any,
) -> None:
    """A lifecycle status cannot substitute for administrator verification."""
    from app.models import Certification

    crew = await _create_test_crew(db_session, "Unverified Valid Medical")
    db_session.add(
        Certification(
            id=str(uuid.uuid4()),
            crew_member_id=crew.id,
            cert_type="OGUK Medical",
            expiry_date=date(2027, 1, 1),
            status="valid",
            verification_status="unverified",
        )
    )
    await db_session.commit()

    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        report = await assignment_service.evaluate_compliance(
            crew_member_id=crew.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 28),
        )

    assert report["status"] == "warning"
    assert any("No offshore medical certificate expiry" in issue for issue in report["issues"])


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
async def test_assignment_negative_day_rate_rejected(db_session: Any) -> None:
    crew = await _create_test_crew(db_session, "Invalid Rate Candidate")
    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        with pytest.raises(ValueError, match="finite non-negative"):
            await assignment_service.create_assignment(
                crew_member_id=crew.id,
                vessel_imo="9111111",
                role_on_board="QC",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 10),
                agreed_day_rate=-1,
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


def test_detached_assignment_graphql_mapping_does_not_fail() -> None:
    """_model_to_graphql_assignment must safely map detached models without triggering DetachedInstanceError."""
    from app.graphql.schema import _model_to_graphql_assignment
    from app.models import CampaignAssignment

    # Create a detached CampaignAssignment model without an active session
    detached = CampaignAssignment(
        id=str(uuid.uuid4()),
        crew_member_id=str(uuid.uuid4()),
        vessel_imo="9111111",
        role_on_board="Chief Scientist",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 28),
        status="confirmed",
        agreed_day_rate=950.0,
    )

    gql_type = _model_to_graphql_assignment(detached)
    assert gql_type.id == detached.id
    assert gql_type.crew_name is None
    assert gql_type.vessel_name is None
    assert gql_type.role_on_board == "Chief Scientist"

    staff_view = _model_to_graphql_assignment(detached, include_commercial=False)
    assert staff_view.agreed_day_rate is None


@pytest.mark.asyncio
async def test_created_assignment_has_relations_loaded_and_graphql_mapped(db_session: Any) -> None:
    """Creating an assignment eagerly loads crew_member, vessel, and maps to GraphQL with names."""
    from app.graphql.schema import _model_to_graphql_assignment

    crew = await _create_test_crew(db_session, "Eager Loaded Specialist")
    with patch("app.services.assignment.get_session_factory", return_value=lambda: db_session):
        assignment = await assignment_service.create_assignment(
            crew_member_id=crew.id,
            vessel_imo="9888888",
            vessel_name="Ocean Pioneer",
            role_on_board="Survey Lead",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 20),
            status="confirmed",
        )

        # Mapping to GraphQL must successfully populate crew_name and vessel_name
        gql_type = _model_to_graphql_assignment(assignment)
        assert gql_type.crew_name == "Eager Loaded Specialist"
        assert gql_type.vessel_name == "Ocean Pioneer"
        assert gql_type.role_on_board == "Survey Lead"
