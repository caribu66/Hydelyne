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
        document_ref="work-history-source.pdf",
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
        id fullName role nationality countryOfResidence gender languages flyingPoint
        email phone dateOfBirth availabilityStatus tags
        passport { number expiry issuingCountry }
        visa { type expiry }
        medical { status expiry provider }
        insurance { provider policyNumber coverage expiry }
        workHistory { id clientName documentRef }
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
    assert target["role"] is None


@pytest.mark.asyncio
async def test_roster_as_staff_is_C1_only(client, db_session, monkeypatch):
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
    # Bulk roster is a C1-only discovery surface. T2 access is reserved for
    # the explicit crewMember detail query.
    assert target["email"] is None
    assert target["phone"] is None
    assert target["workHistory"] == []
    assert target["certifications"][0]["certNumber"] is None
    assert target["dateOfBirth"] is None
    assert target["passport"] is None
    assert target["medical"] is None
    assert target["role"] is None

    search_resp = await client.post(
        "/graphql",
        json={
            "query": """
                query Search {
                    searchCrew(query: "Sensitive Fields Crew") {
                        id email phone dateOfBirth
                    }
                }
            """
        },
    )
    search_body = search_resp.json()
    assert "errors" not in search_body, search_body
    search_target = next(
        member for member in search_body["data"]["searchCrew"] if member["id"] == crew_id
    )
    assert search_target["email"] is None
    assert search_target["phone"] is None
    assert search_target["dateOfBirth"] is None


@pytest.mark.asyncio
async def test_roster_as_admin_is_also_C1_only(client, db_session, monkeypatch):
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
    assert target["email"] is None
    assert target["dateOfBirth"] is None
    assert target["passport"] is None
    assert target["medical"] is None
    assert target["role"] is None


@pytest.mark.asyncio
async def test_staff_create_crew_response_redacts_c3_fields(client, db_session, monkeypatch):
    staff = _make_user("staff")
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation {
                    createCrewMember(
                        fullName: "New Draft Specialist"
                        email: "draft@example.com"
                        dateOfBirth: "1985-05-15"
                        cvSubmission: true
                    ) {
                        id
                        email
                        dateOfBirth
                        passport { number }
                    }
                }
            """
        },
    )

    body = response.json()
    assert "errors" not in body, body
    created = body["data"]["createCrewMember"]
    assert created["email"] == "draft@example.com"
    assert created["dateOfBirth"] is None
    assert created["passport"] is None


# ---------------------------------------------------------------------------
# GraphQL: crewMember detail — same tier logic
# ---------------------------------------------------------------------------

_DETAIL_QUERY = """
query Detail($id: String!) {
    crewMember(id: $id) {
        id fullName email phone dateOfBirth
        passport { number }
        certifications { id certType certNumber }
        workHistory { id clientName documentRef }
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
async def test_me_as_T1_redacts_C2_and_C3(client, db_session, monkeypatch):
    await _create_crew_with_sensitive_fields(db_session)
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.post(
        "/graphql",
        json={"query": "query { me { id fullName email phone passport { number } } }"},
    )
    body = resp.json()
    assert "errors" not in body, body
    m = body["data"]["me"]
    assert m["email"] is None
    assert m["phone"] is None
    assert m["passport"] is None


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
    assert m["workHistory"][0]["documentRef"] == "work-history-source.pdf"


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


@pytest.mark.asyncio
async def test_document_single_staff_hides_orphan_document(client, db_session, monkeypatch):
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=None,
        file_name="orphan.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/orphan.pdf",
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
async def test_expiring_certifications_staff_cannot_read_another_draft(
    client, db_session, monkeypatch
):
    staff_id = str(uuid.uuid4())
    other_staff_id = str(uuid.uuid4())
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("staff", staff_id)),
    )
    draft = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Other Staff Draft",
        role="user",
        publication_status="draft",
        submitted_by=other_staff_id,
    )
    db_session.add(draft)
    await db_session.flush()
    db_session.add(
        Certification(
            id=str(uuid.uuid4()),
            crew_member_id=draft.id,
            cert_type="BOSIET",
            expiry_date=__import__("datetime").date.today(),
            status="expiring_soon",
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/graphql", json={"query": "query { expiringCertifications(days: 30) { id } }"}
    )
    body = resp.json()
    assert "errors" not in body
    assert body["data"]["expiringCertifications"] == []


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
async def test_rest_download_rejects_storage_content_with_wrong_magic_bytes(
    client, db_session, monkeypatch
):
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
        AsyncMock(return_value=_make_user("admin")),
    )
    monkeypatch.setattr(
        "app.services.upload.document_upload_service.get_file_async",
        AsyncMock(return_value=b"not a pdf"),
    )

    resp = await client.get(f"/api/documents/{doc.id}/download")

    assert resp.status_code == 422
    assert resp.json()["detail"] == "Stored document failed validation"


@pytest.mark.asyncio
async def test_rest_download_fails_closed_when_audit_write_fails(client, db_session, monkeypatch):
    """C3 bytes must never leave without an audit entry: if the audit write
    fails, the download fails (retryable 503) instead of serving unlogged
    evidence."""
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
        AsyncMock(return_value=_make_user("admin")),
    )
    monkeypatch.setattr(
        "app.services.upload.document_upload_service.get_file_async",
        AsyncMock(return_value=b"%PDF-1.4\nbytes\n%%EOF"),
    )
    monkeypatch.setattr(
        "app.services.audit.audit_service.log_access",
        AsyncMock(side_effect=RuntimeError("audit db down")),
    )

    resp = await client.get(f"/api/documents/{doc.id}/download")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Download audit unavailable; try again"


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
async def test_rest_status_staff_hides_orphan_document(client, db_session, monkeypatch):
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=None,
        file_name="orphan.pdf",
        file_type="pdf",
        file_size=10,
        storage_type="local",
        storage_path="/tmp/orphan.pdf",
    )
    db_session.add(doc)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("staff")),
    )
    resp = await client.get(f"/api/documents/{doc.id}/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rest_document_search_T1_forbidden(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    resp = await client.get("/api/search/documents?q=test")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rest_document_search_T2_strips_C3(client, db_session, monkeypatch):
    visible_crew_id = str(uuid.uuid4())
    document_id = "doc-1"
    db_session.add(
        CrewMember(
            id=visible_crew_id,
            full_name="Visible Approved Crew",
            publication_status="approved",
        )
    )
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=visible_crew_id,
            file_name="a.pdf",
            file_type="application/pdf",
            file_size=1,
            storage_type="local",
            storage_path="/tmp/a.pdf",
            extraction_status="extracted",
        )
    )
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("staff")),
    )
    with patch.object(
        meilisearch_client,
        "search_documents",
        new=AsyncMock(
            return_value={
                "hits": [
                    {
                        "id": "doc-1",
                        "crew_member_id": visible_crew_id,
                        "extracted_data": {"secret": "x"},
                        "file_name": "a.pdf",
                    }
                ],
                "estimated_total_hits": 1,
            }
        ),
    ) as search_documents:
        resp = await client.get("/api/search/documents?q=test")
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert hits[0].get("extracted_data") is None
    assert hits[0]["file_name"] == "a.pdf"
    assert search_documents.call_args.kwargs["searchable_attributes"] == [
        "file_name",
        "file_type",
        "classification",
    ]


@pytest.mark.asyncio
async def test_rest_document_search_staff_scope_excludes_another_draft(
    client, db_session, monkeypatch
):
    actor = _make_user("staff")
    approved_id = str(uuid.uuid4())
    other_draft_id = str(uuid.uuid4())
    approved_document_id = "approved-doc"
    private_document_id = "private-doc"
    db_session.add_all(
        [
            CrewMember(id=approved_id, full_name="Approved", publication_status="approved"),
            CrewMember(
                id=other_draft_id,
                full_name="Private Draft",
                publication_status="draft",
                submitted_by=str(uuid.uuid4()),
            ),
        ]
    )
    db_session.add_all(
        [
            Document(
                id=approved_document_id,
                crew_member_id=approved_id,
                file_name="approved.pdf",
                file_type="application/pdf",
                file_size=1,
                storage_type="local",
                storage_path="/tmp/approved.pdf",
                extraction_status="extracted",
            ),
            Document(
                id=private_document_id,
                crew_member_id=other_draft_id,
                file_name="private.pdf",
                file_type="application/pdf",
                file_size=1,
                storage_type="local",
                storage_path="/tmp/private.pdf",
                extraction_status="extracted",
            ),
        ]
    )
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=actor),
    )
    with patch.object(
        meilisearch_client,
        "search_documents",
        new=AsyncMock(
            return_value={
                "hits": [
                    {"id": "approved-doc", "crew_member_id": approved_id},
                    {"id": "private-doc", "crew_member_id": other_draft_id},
                ],
                "estimated_total_hits": 2,
            }
        ),
    ) as mocked:
        resp = await client.get("/api/search/documents?q=test")

    assert resp.status_code == 200
    assert [hit["id"] for hit in resp.json()["hits"]] == ["approved-doc"]
    assert f'crew_member_id IN ["{approved_id}"]' in mocked.call_args.kwargs["filters"]


@pytest.mark.asyncio
async def test_rest_document_search_admin_excludes_deleted_and_pending_projection_hits(
    client, db_session, monkeypatch
):
    crew_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(id=crew_id, full_name="Admin Search Crew", publication_status="approved")
    )
    db_session.add(
        Document(
            id="searchable-doc",
            crew_member_id=crew_id,
            file_name="searchable.pdf",
            file_type="application/pdf",
            file_size=1,
            storage_type="local",
            storage_path="/tmp/searchable.pdf",
            extraction_status="approved",
            extracted_data={"current": "yes"},
            extracted_text="current extracted text",
            extraction_confidence={"current": 0.99},
        )
    )
    db_session.add(
        Document(
            id="pending-doc",
            crew_member_id=crew_id,
            file_name="pending.pdf",
            file_type="application/pdf",
            file_size=1,
            storage_type="local",
            storage_path="/tmp/pending.pdf",
            extraction_status="pending",
        )
    )
    db_session.add(
        Document(
            id="orphan-doc",
            crew_member_id=None,
            file_name="orphan.pdf",
            file_type="application/pdf",
            file_size=1,
            storage_type="local",
            storage_path="/tmp/orphan.pdf",
            extraction_status="extracted",
        )
    )
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("admin")),
    )
    with patch.object(
        meilisearch_client,
        "search_documents",
        new=AsyncMock(
            return_value={
                "hits": [
                    {
                        "id": "searchable-doc",
                        "crew_member_id": crew_id,
                        "file_name": "stale-name.pdf",
                        "extracted_data": {"stale": "yes"},
                        "extracted_text": "stale extracted text",
                    },
                    {"id": "orphan-doc", "crew_member_id": None},
                    {"id": "deleted-doc", "crew_member_id": crew_id},
                    {"id": "pending-doc", "crew_member_id": crew_id},
                ],
                "estimated_total_hits": 4,
            }
        ),
    ):
        resp = await client.get("/api/search/documents?q=test")

    assert resp.status_code == 200
    assert [hit["id"] for hit in resp.json()["hits"]] == ["searchable-doc", "orphan-doc"]
    # The page has two authoritative hits, but the provider estimate still
    # describes the full result set rather than this filtered page.
    assert resp.json()["estimated_total_hits"] == 4
    searchable_hit = resp.json()["hits"][0]
    assert searchable_hit["file_name"] == "searchable.pdf"
    assert searchable_hit["extracted_data"] == {"current": "yes"}
    assert searchable_hit["extracted_text"] == "current extracted text"


@pytest.mark.asyncio
async def test_rest_document_search_admin_excludes_documents_owned_by_drafts(
    client, db_session, monkeypatch
):
    approved_id = str(uuid.uuid4())
    draft_id = str(uuid.uuid4())
    db_session.add_all(
        [
            CrewMember(id=approved_id, full_name="Approved", publication_status="approved"),
            CrewMember(id=draft_id, full_name="Unpublished", publication_status="draft"),
            Document(
                id="approved-search-doc",
                crew_member_id=approved_id,
                file_name="approved.pdf",
                file_type="application/pdf",
                file_size=1,
                storage_type="local",
                storage_path="/tmp/approved.pdf",
                extraction_status="extracted",
            ),
            Document(
                id="draft-search-doc",
                crew_member_id=draft_id,
                file_name="draft.pdf",
                file_type="application/pdf",
                file_size=1,
                storage_type="local",
                storage_path="/tmp/draft.pdf",
                extraction_status="extracted",
            ),
        ]
    )
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("admin")),
    )
    with patch.object(
        meilisearch_client,
        "search_documents",
        new=AsyncMock(
            return_value={
                "hits": [
                    {"id": "approved-search-doc", "crew_member_id": approved_id},
                    {"id": "draft-search-doc", "crew_member_id": draft_id},
                ],
                "estimated_total_hits": 2,
            }
        ),
    ):
        response = await client.get("/api/search/documents?q=search")

    assert response.status_code == 200
    assert [hit["id"] for hit in response.json()["hits"]] == ["approved-search-doc"]


@pytest.mark.asyncio
async def test_rest_document_search_rechecks_requested_crew_against_source(
    client, db_session, monkeypatch
):
    """A stale projection must not satisfy a filter for a former owner."""
    former_owner_id = str(uuid.uuid4())
    current_owner_id = str(uuid.uuid4())
    db_session.add_all(
        [
            CrewMember(id=former_owner_id, full_name="Former Owner", publication_status="approved"),
            CrewMember(
                id=current_owner_id, full_name="Current Owner", publication_status="approved"
            ),
            Document(
                id="reassigned-doc",
                crew_member_id=current_owner_id,
                file_name="reassigned.pdf",
                file_type="application/pdf",
                file_size=1,
                storage_type="local",
                storage_path="/tmp/reassigned.pdf",
                extraction_status="extracted",
            ),
        ]
    )
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("admin")),
    )
    with patch.object(
        meilisearch_client,
        "search_documents",
        new=AsyncMock(
            return_value={
                "hits": [{"id": "reassigned-doc", "crew_member_id": former_owner_id}],
                "estimated_total_hits": 1,
            }
        ),
    ):
        response = await client.get(
            "/api/search/documents",
            params={"q": "reassigned", "crew_id": former_owner_id},
        )

    assert response.status_code == 200
    assert response.json()["hits"] == []
    # The provider estimate is retained because this response represents only
    # one page, even though that stale hit was removed from the returned data.
    assert response.json()["estimated_total_hits"] == 1


@pytest.mark.asyncio
async def test_rest_crew_search_strips_denied_fields(client, db_session, monkeypatch):
    db_session.add(CrewMember(id="crew-1", full_name="A", publication_status="approved"))
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("user")),
    )
    with patch.object(
        meilisearch_client,
        "search_crew_members",
        new=AsyncMock(
            return_value={
                "hits": [
                    {
                        "id": "crew-1",
                        "full_name": "A",
                        "email": "a@b.com",
                        "phone": "123",
                        "internal_notes": "private",
                        "role": "admin",
                        "submitted_by": "owner",
                    }
                ],
                "estimated_total_hits": 1,
            }
        ),
    ):
        resp = await client.get("/api/search/crew?q=test")
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert "email" not in hits[0]
    assert "phone" not in hits[0]
    assert "internal_notes" not in hits[0]
    assert "role" not in hits[0]
    assert "submitted_by" not in hits[0]


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


@pytest.mark.asyncio
async def test_dropbox_download_admin_returns_file_bytes(client, db_session, monkeypatch):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Dropbox Download Crew")
    db_session.add(crew)
    await db_session.flush()
    doc_id = str(uuid.uuid4())
    managed_path = f"/hydenlyne/{crew.id}/documents/misc/{doc_id}_certificate.pdf"
    doc = Document(
        id=doc_id,
        crew_member_id=crew.id,
        file_name="certificate.pdf",
        file_type="pdf",
        file_size=4,
        storage_type="dropbox",
        storage_path=managed_path,
        dropbox_path=managed_path,
    )
    db_session.add(doc)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("admin")),
    )
    with patch(
        "app.api.dropbox.download_dropbox_content",
        new=AsyncMock(return_value=(200, b"%PDF-1.4")),
    ):
        result = await client.post(f"/api/dropbox/download/{doc.id}")

    assert result.status_code == 200
    assert result.content == b"%PDF-1.4"
    assert result.headers["content-disposition"].startswith(
        'attachment; filename="certificate.pdf"'
    )


@pytest.mark.asyncio
async def test_dropbox_download_admin_rejects_wrong_magic_bytes(client, db_session, monkeypatch):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Invalid Dropbox Crew")
    db_session.add(crew)
    await db_session.flush()
    doc_id = str(uuid.uuid4())
    managed_path = f"/hydenlyne/{crew.id}/documents/misc/{doc_id}_certificate.pdf"
    doc = Document(
        id=doc_id,
        crew_member_id=crew.id,
        file_name="certificate.pdf",
        file_type="pdf",
        file_size=10,
        storage_type="dropbox",
        storage_path=managed_path,
        dropbox_path=managed_path,
    )
    db_session.add(doc)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token",
        AsyncMock(return_value=_make_user("admin")),
    )
    with patch(
        "app.api.dropbox.download_dropbox_content",
        new=AsyncMock(return_value=(200, b"not a pdf")),
    ):
        result = await client.post(f"/api/dropbox/download/{doc.id}")

    assert result.status_code == 422
    assert result.json()["detail"] == "Stored document failed validation"
