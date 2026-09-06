"""Negative authorization tests for field-level access tiers (ADR 0005).

Every restricted field, document classification, and download route must be
proven to deny T1 callers. These tests assert fail-closed behavior:
- T1 (role=user) sees C1 only or null/empty for C2/C3, never the value.
- T2 (role=staff) sees C1+C2 but not C3.
- T3 (role=admin) sees all.

Covers:
- GraphQL roster (crewMembers) and profile (crewMember) field redaction
- GraphQL documents / documentsByCrew tier gating and C3 scrubbing
- GraphQL expiringCertifications (T2+), complianceStatus (T3), generateReport (T2+ for sensitive types)
- REST document download (T3), status (T2), document search (T2 with C3 stripping)
- Meilisearch general projection is C1-only (no email/phone/passport/medical)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models import Certification, CrewMember, Document
from app.services.meilisearch import meilisearch_client


def _make_user(role: str, user_id: str | None = None) -> CrewMember:
    return CrewMember(
        id=user_id or str(uuid.uuid4()),
        full_name=f"{role.title()} User",
        email=f"{role}@test.com",
        role=role,
    )


async def _create_crew_with_sensitive_fields(db_session) -> str:
    """Create an approved crew with C2 and C3 data for tier checks."""
    crew_id = str(uuid.uuid4())
    crew = CrewMember(
        id=crew_id,
        full_name="Sensitive Fields Crew",
        email="sensitive@example.com",
        phone="+44 7000 999999",
        nationality="British",
        country_of_residence="UK",
        date_of_birth=__import__("datetime").date(1985, 5, 15),
        gender="male",
        languages=["English"],
        flying_point="London",
        passport_number="GBR123456",
        passport_expiry=__import__("datetime").date(2030, 1, 1),
        passport_issuing_country="GBR",
        visa_type="work",
        visa_restrictions="none",
        visa_expiry=__import__("datetime").date(2030, 6, 1),
        medical_status="fit",
        medical_expiry=__import__("datetime").date(2030, 12, 31),
        medical_provider="OGUK",
        insurance_provider="InsureCo",
        insurance_policy_number="POL-999",
        insurance_coverage="full",
        insurance_expiry=__import__("datetime").date(2030, 12, 31),
        availability_status="available",
        internal_notes="internal note content",
        publication_status="approved",
    )
    db_session.add(crew)
    await db_session.flush()
    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        cert_type="BOSIET",
        cert_number="BOSIET-123",
        issuing_body="OPITO",
        issue_date=__import__("datetime").date(2022, 1, 1),
        expiry_date=__import__("datetime").date(2026, 1, 1),
        renewal_date=__import__("datetime").date(2025, 12, 1),
        status="valid",
        document_ref="doc-123",
        extracted_confidence=0.99,
        verification_status="verified",
    )
    db_session.add(cert)
    # Add work history (C2)
    from app.models import WorkHistory

    wh = WorkHistory(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        client_name="Acme Client",
        project_name="North Sea Job",
        country="UK",
        role="Surveyor",
    )
    db_session.add(wh)
    await db_session.commit()
    return crew_id


# ---------------------------------------------------------------------------
# GraphQL: crewMembers roster is tier-scoped — T1 must not see C2/C3
# ---------------------------------------------------------------------------

_ROSTER_QUERY = """
query Roster {
    crewMembers(limit: 10, offset: 0) {
        id fullName nationality countryOfResidence gender languages flyingPoint
        email phone dateOfBirth availabilityStatus tags
        passport { number expiry issuingCountry }
        visa { type expiry }
        medical { status expiry provider }
        insurance { provider policyNumber coverage expiry }
        workHistory { id clientName }
        certifications { id certType certNumber issuingBody renewalDate documentRef }
        internalNotes
    }
}
"""


@pytest.mark.asyncio
async def test_roster_as_T1_redacts_C2_and_C3(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    user = _make_user("user")
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=user)
    )

    resp = await client.post("/graphql", json={"query": _ROSTER_QUERY})
    body = resp.json()
    assert "errors" not in body, body
    members = body["data"]["crewMembers"]
    # Find our crew
    target = next((m for m in members if m["id"] == crew_id), None)
    assert target is not None, "crew not in roster (maybe pagination)"
    # C2 fields must be absent/null for T1
    assert target["email"] is None
    assert target["phone"] is None
    assert target["internalNotes"] is None
    assert target["workHistory"] == []
    assert target["certifications"][0]["certNumber"] is None
    assert target["certifications"][0]["issuingBody"] is None
    # C3 fields must be null
    assert target["dateOfBirth"] is None
    assert target["passport"] is None
    assert target["visa"] is None
    assert target["medical"] is None
    assert target["insurance"] is None
    # C1 fields must remain
    assert target["fullName"] == "Sensitive Fields Crew"
    assert target["nationality"] == "British"


@pytest.mark.asyncio
async def test_roster_as_staff_shows_C2_but_not_C3(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    staff = _make_user("staff")
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )

    resp = await client.post("/graphql", json={"query": _ROSTER_QUERY})
    body = resp.json()
    assert "errors" not in body, body
    target = next((m for m in body["data"]["crewMembers"] if m["id"] == crew_id), None)
    assert target is not None
    # T2 sees C2
    assert target["email"] == "sensitive@example.com"
    assert target["phone"] == "+44 7000 999999"
    assert len(target["workHistory"]) == 1
    assert target["certifications"][0]["certNumber"] == "BOSIET-123"
    # T2 must not see C3
    assert target["dateOfBirth"] is None
    assert target["passport"] is None
    assert target["medical"] is None


@pytest.mark.asyncio
async def test_roster_as_admin_shows_all(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    admin = _make_user("admin")
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=admin)
    )

    resp = await client.post("/graphql", json={"query": _ROSTER_QUERY})
    body = resp.json()
    assert "errors" not in body, body
    target = next((m for m in body["data"]["crewMembers"] if m["id"] == crew_id), None)
    assert target is not None
    assert target["email"] == "sensitive@example.com"
    assert target["dateOfBirth"] is not None
    assert target["passport"] is not None
    assert target["passport"]["number"] == "GBR123456"
    assert target["medical"] is not None


# ---------------------------------------------------------------------------
# GraphQL: crewMember detail — same tier logic
# ---------------------------------------------------------------------------

_DETAIL_QUERY = """
query Detail($id: String!) {
    crewMember(id: $id) {
        id fullName email phone dateOfBirth
        passport { number }
        certifications { id certType certNumber }
        workHistory { id clientName }
        internalNotes
    }
}
"""


@pytest.mark.asyncio
async def test_detail_as_T1_redacts_C2_and_C3(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.post(
        "/graphql", json={"query": _DETAIL_QUERY, "variables": {"id": crew_id}}
    )
    body = resp.json()
    assert "errors" not in body, body
    m = body["data"]["crewMember"]
    assert m["email"] is None
    assert m["phone"] is None
    assert m["dateOfBirth"] is None
    assert m["passport"] is None
    assert m["workHistory"] == []
    assert m["certifications"][0]["certNumber"] is None


@pytest.mark.asyncio
async def test_detail_as_staff_shows_C2_not_C3(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("staff")),
    )
    resp = await client.post(
        "/graphql", json={"query": _DETAIL_QUERY, "variables": {"id": crew_id}}
    )
    body = resp.json()
    assert "errors" not in body
    m = body["data"]["crewMember"]
    assert m["email"] == "sensitive@example.com"
    assert m["passport"] is None


# ---------------------------------------------------------------------------
# GraphQL: documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_documents_by_crew_T1_returns_empty(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        file_name="cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/cert.pdf",
        extracted_text="secret extracted",
        extracted_data={"secret": "data"},
    )
    db_session.add(doc)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.post(
        "/graphql",
        json={
            "query": "query($crewId: String!) { documentsByCrew(crewId: $crewId) { id fileName extractedText extractedData } }",
            "variables": {"crewId": crew_id},
        },
    )
    body = resp.json()
    assert "errors" not in body
    assert body["data"]["documentsByCrew"] == []


@pytest.mark.asyncio
async def test_documents_by_crew_T2_strips_C3(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        file_name="cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/cert.pdf",
        extraction_status="extracted",
        extracted_text="secret extracted",
        extracted_data={"secret": "data"},
    )
    db_session.add(doc)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("staff")),
    )
    resp = await client.post(
        "/graphql",
        json={
            "query": "query($crewId: String!) { documentsByCrew(crewId: $crewId) { id fileName extractedText extractedData } }",
            "variables": {"crewId": crew_id},
        },
    )
    body = resp.json()
    assert "errors" not in body
    docs = body["data"]["documentsByCrew"]
    assert len(docs) == 1
    assert docs[0]["extractedText"] is None
    assert docs[0]["extractedData"] is None


@pytest.mark.asyncio
async def test_documents_by_crew_T3_shows_C3(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        file_name="cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/cert.pdf",
        extraction_status="extracted",
        extracted_text="secret extracted",
        extracted_data={"secret": "data"},
    )
    db_session.add(doc)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("admin")),
    )
    resp = await client.post(
        "/graphql",
        json={
            "query": "query($crewId: String!) { documentsByCrew(crewId: $crewId) { id fileName extractedText extractedData } }",
            "variables": {"crewId": crew_id},
        },
    )
    body = resp.json()
    assert "errors" not in body
    docs = body["data"]["documentsByCrew"]
    assert docs[0]["extractedText"] == "secret extracted"


@pytest.mark.asyncio
async def test_document_single_T1_returns_null(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        file_name="cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/cert.pdf",
        extracted_text="secret",
    )
    db_session.add(doc)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.post(
        "/graphql",
        json={
            "query": "query($id: String!) { document(id: $id) { id fileName } }",
            "variables": {"id": doc.id},
        },
    )
    body = resp.json()
    assert "errors" not in body
    assert body["data"]["document"] is None


# ---------------------------------------------------------------------------
# GraphQL: compliance + expiring + report gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expiring_certifications_T1_forbidden(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.post(
        "/graphql", json={"query": "query { expiringCertifications(days: 30) { id } }"}
    )
    body = resp.json()
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


@pytest.mark.asyncio
async def test_expiring_certifications_T2_allowed(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("staff")),
    )
    resp = await client.post(
        "/graphql", json={"query": "query { expiringCertifications(days: 30) { id } }"}
    )
    body = resp.json()
    assert "errors" not in body


@pytest.mark.asyncio
async def test_compliance_status_T1_forbidden(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.post(
        "/graphql",
        json={
            "query": "query($id: String!) { complianceStatus(crewId: $id) }",
            "variables": {"id": crew_id},
        },
    )
    body = resp.json()
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


@pytest.mark.asyncio
async def test_compliance_status_T2_forbidden(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("staff")),
    )
    resp = await client.post(
        "/graphql",
        json={
            "query": "query($id: String!) { complianceStatus(crewId: $id) }",
            "variables": {"id": crew_id},
        },
    )
    body = resp.json()
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


@pytest.mark.asyncio
async def test_compliance_status_admin_allowed(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("admin")),
    )
    resp = await client.post(
        "/graphql",
        json={
            "query": "query($id: String!) { complianceStatus(crewId: $id) }",
            "variables": {"id": crew_id},
        },
    )
    body = resp.json()
    assert "errors" not in body, body
    assert "complianceStatus" in body["data"]


@pytest.mark.asyncio
async def test_generate_report_compliance_T1_forbidden(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.post(
        "/graphql",
        json={"query": "query { generateReport(reportType: COMPLIANCE) { reportType } }"},
    )
    body = resp.json()
    assert "errors" in body
    assert any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in body["errors"])


@pytest.mark.asyncio
async def test_generate_report_availability_T1_allowed(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    # Mock report generation to avoid LLM
    with patch(
        "app.services.reports.report_service.generate_report",
        new=AsyncMock(side_effect=RuntimeError("llm")),
    ):
        resp = await client.post(
            "/graphql",
            json={"query": "query { generateReport(reportType: AVAILABILITY) { reportType } }"},
        )
    body = resp.json()
    assert "errors" not in body, body
    assert body["data"]["generateReport"]["reportType"] == "availability"


# ---------------------------------------------------------------------------
# REST: download / status / document search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rest_download_T1_forbidden(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        file_name="secret.pdf",
        file_type="pdf",
        file_size=10,
        storage_type="local",
        storage_path="/tmp/secret.pdf",
    )
    db_session.add(doc)
    await db_session.commit()
    # Mock file content so admin case would succeed if authorized
    monkeypatch.setattr(
        "app.services.upload.document_upload_service.get_file", lambda path: b"bytes"
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.get(f"/api/documents/{doc.id}/download")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rest_download_T2_forbidden(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        file_name="secret.pdf",
        file_type="pdf",
        file_size=10,
        storage_type="local",
        storage_path="/tmp/secret.pdf",
    )
    db_session.add(doc)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("staff")),
    )
    resp = await client.get(f"/api/documents/{doc.id}/download")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rest_status_T1_forbidden(client, db_session, monkeypatch):
    crew_id = await _create_crew_with_sensitive_fields(db_session)
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        file_name="secret.pdf",
        file_type="pdf",
        file_size=10,
        storage_type="local",
        storage_path="/tmp/secret.pdf",
    )
    db_session.add(doc)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.get(f"/api/documents/{doc.id}/status")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rest_document_search_T1_forbidden(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.get("/api/search/documents?q=test")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rest_document_search_T2_strips_C3(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("staff")),
    )
    with patch.object(
        meilisearch_client,
        "search_documents",
        new=AsyncMock(
            return_value={
                "hits": [{"id": "doc-1", "extracted_data": {"secret": "x"}, "file_name": "a.pdf"}],
                "estimated_total_hits": 1,
            }
        ),
    ):
        resp = await client.get("/api/search/documents?q=test")
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert hits[0].get("extracted_data") is None
    assert hits[0]["file_name"] == "a.pdf"


@pytest.mark.asyncio
async def test_rest_crew_search_strips_denied_fields(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    with patch.object(
        meilisearch_client,
        "search_crew_members",
        new=AsyncMock(
            return_value={
                "hits": [{"id": "crew-1", "full_name": "A", "email": "a@b.com", "phone": "123"}],
                "estimated_total_hits": 1,
            }
        ),
    ):
        resp = await client.get("/api/search/crew?q=test")
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert "email" not in hits[0]
    assert "phone" not in hits[0]


# ---------------------------------------------------------------------------
# Meilisearch projection is C1-only
# ---------------------------------------------------------------------------


def test_meilisearch_doc_is_C1_only():
    from app.services.consultant_knowledge import _crew_meilisearch_doc

    crew = CrewMember(
        id="test-id",
        full_name="Test Crew",
        email="should-not-be-indexed@example.com",
        phone="000",
        passport_number="GBR999",
        medical_status="fit",
        nationality="British",
        availability_status="available",
        tags=["BOSIET"],
        publication_status="approved",
        education="MSc",
    )
    doc = _crew_meilisearch_doc(crew)
    assert doc["full_name"] == "Test Crew"
    assert "email" not in doc
    assert "phone" not in doc
    assert "passport_number" not in doc
    assert "medical_status" not in doc
    assert "extracted_data" not in doc
    assert doc["publication_status"] == "approved"


@pytest.mark.asyncio
async def test_dropbox_download_T1_forbidden(client, monkeypatch):
    # Dropbox download is also T3 — create doc directly
    from tests.conftest import test_session_factory

    async with test_session_factory() as session:
        crew = CrewMember(
            id=str(uuid.uuid4()), full_name="Dropbox Crew", publication_status="approved"
        )
        session.add(crew)
        await session.flush()
        doc = Document(
            id=str(uuid.uuid4()),
            crew_member_id=crew.id,
            file_name="drop.pdf",
            file_type="pdf",
            file_size=10,
            storage_type="dropbox",
            storage_path="/hydenlyne/crew/drop.pdf",
            dropbox_path="/hydenlyne/crew/drop.pdf",
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.post(f"/api/dropbox/download/{doc_id}")
    assert resp.status_code == 403
