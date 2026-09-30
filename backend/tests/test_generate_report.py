"""Characterization tests for the generateReport GraphQL mutation.

Written before extracting the ~100-line deterministic report-data-building
block out of app/graphql/schema.py's generate_report resolver and into
app/services/reports.py (docs/AUDIT_2026-09-02.md P2 #9 — large files;
P2 #10 — GraphQL schema doing direct database orchestration). This resolver
had zero prior test coverage, so these lock in the exact current behavior —
both the LLM-enriched success path and the deterministic fallback when the
LLM call fails — before anything moves.
"""

import json
import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models import Certification, CrewMember, Document, Project
from app.services.reports import _derived_certification_status, validate_report_filters


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def _mock_admin_user(monkeypatch: pytest.MonkeyPatch) -> CrewMember:
    admin = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Admin User",
        email="admin@test.com",
        role="admin",
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=admin),
    )
    return admin


def test_report_filter_shape_rejects_non_string_status():
    with pytest.raises(ValueError, match="status must be a string"):
        validate_report_filters("compliance", {"status": 1})


def test_report_filter_shape_rejects_mixed_status_list():
    with pytest.raises(ValueError, match="status must be a string"):
        validate_report_filters("compliance", {"status": ["expired", 30]})


def test_report_filter_rejects_unbounded_status_list():
    with pytest.raises(ValueError, match="at most 20"):
        validate_report_filters("compliance", {"status": ["expired"] * 21})


def test_report_filter_rejects_oversized_status_value():
    with pytest.raises(ValueError, match="overly long"):
        validate_report_filters("compliance", {"status": ["x" * 101]})


def test_report_filter_rejects_unknown_certification_status():
    with pytest.raises(ValueError, match="Invalid certification status"):
        validate_report_filters("compliance", {"status": "not-a-status"})
    with pytest.raises(ValueError, match="Invalid certification status"):
        validate_report_filters("compliance", {"status": ["expired", "unknown"]})


def test_project_report_filter_rejects_unknown_status():
    with pytest.raises(ValueError, match="Invalid project status"):
        validate_report_filters("project_readiness", {"status": "not-a-status"})


def test_report_filter_rejects_empty_certification_status_list():
    with pytest.raises(ValueError, match="at least one value"):
        validate_report_filters("compliance", {"status": []})


def test_report_certification_status_uses_verified_expiry_evidence():
    reference_date = date(2026, 9, 13)

    assert _derived_certification_status(date(2027, 1, 1), "verified", reference_date) == "valid"
    assert (
        _derived_certification_status(date(2026, 9, 20), "verified", reference_date)
        == "expiring_soon"
    )
    assert _derived_certification_status(date(2026, 9, 12), "verified", reference_date) == "expired"
    assert (
        _derived_certification_status(None, "unverified", reference_date) == "pending_verification"
    )


_GENERATE_REPORT_QUERY = """
    query($reportType: ReportType!) {
        generateReport(reportType: $reportType) {
            reportType
            summary
            data
        }
    }
"""


@pytest.mark.asyncio
async def test_availability_report_counts_only_available_crew(client, db_session, monkeypatch):
    _mock_admin_user(monkeypatch)
    monkeypatch.setattr(
        "app.services.reports.report_service.generate_report",
        AsyncMock(side_effect=RuntimeError("LLM unavailable in test")),
    )
    db_session.add_all(
        [
            CrewMember(
                id=str(uuid.uuid4()),
                full_name="Available One",
                role="user",
                availability_status="available",
            ),
            CrewMember(
                id=str(uuid.uuid4()),
                full_name="On Assignment",
                role="user",
                availability_status="on_assignment",
            ),
            CrewMember(
                id=str(uuid.uuid4()),
                full_name="Admin Login Account",
                role="admin",
                password_hash="stored-password-hash",
                availability_status="available",
            ),
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/graphql",
        headers=_admin_headers(),
        json={
            "query": _GENERATE_REPORT_QUERY,
            "variables": {"reportType": "AVAILABILITY"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    report = body["data"]["generateReport"]
    assert report["reportType"] == "availability"
    assert "1 crew members currently available" in report["summary"]


@pytest.mark.asyncio
async def test_staff_report_scope_excludes_other_drafts(db_session):
    from app.services.reports import report_service

    owner_id = str(uuid.uuid4())
    other_owner_id = str(uuid.uuid4())
    db_session.add_all(
        [
            CrewMember(
                id=str(uuid.uuid4()),
                full_name="Approved",
                availability_status="available",
                publication_status="approved",
            ),
            CrewMember(
                id=str(uuid.uuid4()),
                full_name="Own Draft",
                availability_status="available",
                publication_status="draft",
                submitted_by=owner_id,
            ),
            CrewMember(
                id=str(uuid.uuid4()),
                full_name="Other Draft",
                availability_status="available",
                publication_status="draft",
                submitted_by=other_owner_id,
            ),
        ]
    )
    await db_session.commit()

    data = await report_service.build_report_data(
        "availability",
        db_session,
        actor_id=owner_id,
        actor_role="staff",
    )

    assert data["available_count"] == 2
    assert {row["name"] for row in data["crew"]} == {"Approved", "Own Draft"}


@pytest.mark.asyncio
async def test_staff_project_report_hides_unpublished_assigned_crew(db_session):
    from app.services.reports import report_service

    owner_id = str(uuid.uuid4())
    approved_id = str(uuid.uuid4())
    own_draft_id = str(uuid.uuid4())
    other_draft_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())
    db_session.add_all(
        [
            CrewMember(id=approved_id, full_name="Approved", publication_status="approved"),
            CrewMember(
                id=own_draft_id,
                full_name="Own Draft",
                publication_status="draft",
                submitted_by=owner_id,
            ),
            CrewMember(
                id=other_draft_id,
                full_name="Other Draft",
                publication_status="draft",
                submitted_by=str(uuid.uuid4()),
            ),
            CrewMember(
                id=account_id,
                full_name="Admin Account",
                role="admin",
                password_hash="stored-password-hash",
                publication_status="approved",
            ),
            Project(
                id=str(uuid.uuid4()),
                client_name="Client",
                project_name="Project",
                project_type="environmental",
                crew_assigned=[approved_id, own_draft_id, other_draft_id, account_id],
            ),
        ]
    )
    await db_session.commit()

    data = await report_service.build_report_data(
        "project_readiness",
        db_session,
        actor_id=owner_id,
        actor_role="staff",
    )

    assert data["projects"][0]["crew_assigned"] == [approved_id, own_draft_id]

    admin_data = await report_service.build_report_data(
        "project_readiness",
        db_session,
        actor_role="admin",
    )

    assert set(admin_data["projects"][0]["crew_assigned"]) == {
        approved_id,
        own_draft_id,
        other_draft_id,
    }


@pytest.mark.asyncio
async def test_compliance_report_counts_expired_and_expiring_certifications(
    client, db_session, monkeypatch
):
    _mock_admin_user(monkeypatch)
    monkeypatch.setattr(
        "app.services.reports.report_service.generate_report",
        AsyncMock(side_effect=RuntimeError("LLM unavailable in test")),
    )
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Crew", role="user")
    expiring_date = date.today() + timedelta(days=10)
    db_session.add(crew)
    await db_session.flush()
    db_session.add_all(
        [
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="bosiet",
                status="expired",
                verification_status="verified",
                expiry_date=date(2020, 1, 1),
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="huet",
                status="expiring_soon",
                verification_status="verified",
                expiry_date=expiring_date,
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="medical",
                status="valid",
                expiry_date=date(2030, 1, 1),
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="unverified-expired",
                status="expired",
                verification_status="unverified",
                expiry_date=date(2020, 1, 1),
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="rejected-bosiet",
                status="expired",
                verification_status="rejected",
                expiry_date=date(2020, 1, 1),
            ),
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/graphql",
        headers=_admin_headers(),
        json={
            "query": _GENERATE_REPORT_QUERY,
            "variables": {"reportType": "COMPLIANCE"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    report = body["data"]["generateReport"]
    assert report["reportType"] == "compliance"
    assert "2 certifications require attention" in report["summary"]


@pytest.mark.asyncio
async def test_project_readiness_report_counts_all_projects(client, db_session, monkeypatch):
    _mock_admin_user(monkeypatch)
    monkeypatch.setattr(
        "app.services.reports.report_service.generate_report",
        AsyncMock(side_effect=RuntimeError("LLM unavailable in test")),
    )
    db_session.add(
        Project(
            id=str(uuid.uuid4()),
            client_name="Client",
            project_name="Project One",
            project_type="marine_seismic",
            status="active",
        )
    )
    await db_session.commit()

    response = await client.post(
        "/graphql",
        headers=_admin_headers(),
        json={
            "query": _GENERATE_REPORT_QUERY,
            "variables": {"reportType": "PROJECT_READINESS"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    report = body["data"]["generateReport"]
    assert report["reportType"] == "project_readiness"
    assert "Project_Readiness report generated successfully" in report["summary"]


@pytest.mark.asyncio
async def test_performance_report_counts_performance_documents(client, db_session, monkeypatch):
    _mock_admin_user(monkeypatch)
    monkeypatch.setattr(
        "app.services.reports.report_service.generate_report",
        AsyncMock(side_effect=RuntimeError("LLM unavailable in test")),
    )
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    db_session.add_all(
        [
            Document(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                file_name="perf.pdf",
                file_type="application/pdf",
                file_size=10,
                storage_path="/tmp/perf.pdf",
                storage_type="local",
                classification="performance",
                extraction_status="extracted",
            ),
            Document(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                file_name="pending-perf.pdf",
                file_type="application/pdf",
                file_size=10,
                storage_path="/tmp/pending-perf.pdf",
                storage_type="local",
                classification="performance",
                extraction_status="pending",
            ),
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/graphql",
        headers=_admin_headers(),
        json={
            "query": _GENERATE_REPORT_QUERY,
            "variables": {"reportType": "PERFORMANCE"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    report = body["data"]["generateReport"]
    assert report["reportType"] == "performance"
    report_data = json.loads(report["data"])
    assert report_data["performance_document_count"] == 1
    assert [doc["file_name"] for doc in report_data["documents"]] == ["perf.pdf"]


@pytest.mark.asyncio
async def test_llm_enriched_report_uses_ai_service_response_when_available(client, monkeypatch):
    _mock_admin_user(monkeypatch)
    monkeypatch.setattr(
        "app.services.reports.report_service.generate_report",
        AsyncMock(
            return_value={
                "id": "report-1",
                "title": "Custom Title",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "summary": "AI-generated summary",
                "data": '{"ai": true}',
                "recommendations": "[]",
            }
        ),
    )

    response = await client.post(
        "/graphql",
        headers=_admin_headers(),
        json={
            "query": _GENERATE_REPORT_QUERY,
            "variables": {"reportType": "AVAILABILITY"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    report = body["data"]["generateReport"]
    assert report["summary"] == "AI-generated summary"
    assert report["data"] == '{"ai": true}'


@pytest.mark.asyncio
async def test_malformed_filters_return_bad_input_not_500(client, monkeypatch):
    _mock_admin_user(monkeypatch)
    resp = await client.post(
        "/graphql",
        json={
            "query": "query($t: ReportType!, $f: String) { generateReport(reportType: $t, filters: $f) { reportType } }",
            "variables": {"t": "AVAILABILITY", "f": "{not-json"},
        },
        headers=_admin_headers(),
    )
    body = resp.json()
    assert "errors" in body
    assert body["errors"][0]["extensions"]["code"] == "BAD_USER_INPUT"


def test_graphql_json_parser_rejects_non_standard_numbers():
    from graphql import GraphQLError

    from app.graphql.schema import _parse_json_object

    with pytest.raises(GraphQLError, match="Invalid JSON for filters"):
        _parse_json_object('{"status": NaN}', field="filters")


@pytest.mark.asyncio
async def test_report_model_non_scalar_summary_is_not_returned_as_graphql_text(monkeypatch):
    from app.services.reports import ReportService

    monkeypatch.setattr(
        "app.services.reports.ollama_client.extract",
        AsyncMock(return_value={"response": '{"summary": ["not text"]}'}),
    )

    report = await ReportService().generate_report("availability", {})

    assert report["summary"] == ""


@pytest.mark.asyncio
async def test_report_model_payload_is_typed_and_bounded(monkeypatch):
    from app.services.reports import ReportService

    monkeypatch.setattr(
        "app.services.reports.ollama_client.extract",
        AsyncMock(
            return_value={
                "response": json.dumps(
                    {
                        "summary": "s" * 3_000,
                        "total_available": 4,
                        "secret": "unexpected model-controlled field",
                        "recommendations": ["r" * 600] * 21,
                    }
                )
            }
        ),
    )

    report = await ReportService().generate_report("availability", {})
    payload = json.loads(report["data"])

    assert len(payload["summary"]) == 2_000
    assert payload["total_available"] == 4
    assert "secret" not in payload
    assert len(payload["recommendations"]) == 20
    assert len(payload["recommendations"][0]) == 500


@pytest.mark.asyncio
async def test_report_model_invalid_output_is_not_persisted(monkeypatch):
    from app.services.reports import ReportService

    leaked_content = "passport-number-or-cv-content " * 1000
    monkeypatch.setattr(
        "app.services.reports.ollama_client.extract",
        AsyncMock(return_value={"response": leaked_content}),
    )

    report = await ReportService().generate_report("availability", {})

    assert report["summary"] == "The report model returned an invalid response."
    assert leaked_content not in report["data"]
    assert "raw_response" not in report["data"]
