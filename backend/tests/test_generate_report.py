"""Characterization tests for the generateReport GraphQL mutation.

Written before extracting the ~100-line deterministic report-data-building
block out of app/graphql/schema.py's generate_report resolver and into
app/services/reports.py (docs/AUDIT_2026-09-02.md P2 #9 — large files;
P2 #10 — GraphQL schema doing direct database orchestration). This resolver
had zero prior test coverage, so these lock in the exact current behavior —
both the LLM-enriched success path and the deterministic fallback when the
LLM call fails — before anything moves.
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.models import Certification, CrewMember, Document, Project


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
async def test_compliance_report_counts_expired_and_expiring_certifications(
    client, db_session, monkeypatch
):
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
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="bosiet",
                status="expired",
                expiry_date=date(2020, 1, 1),
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="huet",
                status="expiring_soon",
                expiry_date=date(2030, 1, 1),
            ),
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew.id,
                cert_type="medical",
                status="valid",
                expiry_date=date(2030, 1, 1),
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
    db_session.add(
        Document(
            id=str(uuid.uuid4()),
            crew_member_id=crew.id,
            file_name="perf.pdf",
            file_type="application/pdf",
            file_size=10,
            storage_path="/tmp/perf.pdf",
            storage_type="local",
            classification="performance",
        )
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
