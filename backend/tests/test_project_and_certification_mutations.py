"""Characterization tests for reprocessDocument/updateCertification/
verifyCertification/createProject/updateProject/assignCrewToProject.

Written before extracting their inline SQLAlchemy queries out of
app/graphql/schema.py (slice 3 of the decomposition — see
docs/CHANGELOG.md slices 1 and 2). Each of these six resolvers previously
had only negative-authorization (FORBIDDEN) coverage in test_auth.py —
zero prior test verified their actual success-path behavior. conftest.py's
default test identity is already an admin, so no auth mocking is needed
here (mirrors tests/test_crew.py's convention).
"""

import uuid
from datetime import date, datetime
from unittest.mock import patch

import pytest

from app.models import (
    Certification,
    CrewMember,
    CVReview,
    Document,
    DocumentRequest,
    IncomingDocumentReview,
    Project,
)


@pytest.mark.asyncio
async def test_reprocess_document_resets_extraction_status_to_pending(client, db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="cv.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="/tmp/cv.pdf",
        storage_type="local",
        extraction_status="failed",
    )
    db_session.add(doc)
    await db_session.commit()

    with patch("app.tasks.document_tasks.process_document_extraction.delay") as dispatch:
        response = await client.post(
            "/graphql",
            json={
                "query": """
                    mutation($id: String!) {
                        reprocessDocument(documentId: $id) { id extractionStatus }
                    }
                """,
                "variables": {"id": doc.id},
            },
        )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["reprocessDocument"]["extractionStatus"] == "pending"
    dispatch.assert_called_once_with(doc.id)


@pytest.mark.asyncio
async def test_reprocess_marks_document_failed_when_dispatch_fails(client, db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Dispatch Failure Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="retry.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="/tmp/retry.pdf",
        storage_type="local",
        extraction_status="failed",
    )
    db_session.add(doc)
    await db_session.commit()

    with patch(
        "app.tasks.document_tasks.process_document_extraction.delay",
        side_effect=RuntimeError("broker unavailable"),
    ):
        response = await client.post(
            "/graphql",
            json={
                "query": """
                    mutation($id: String!) {
                        reprocessDocument(documentId: $id) { id extractionStatus }
                    }
                """,
                "variables": {"id": doc.id},
            },
        )

    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["reprocessDocument"]["extractionStatus"] == "failed"


@pytest.mark.asyncio
async def test_reprocess_approved_certificate_detaches_stale_projection(client, db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Certificate Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="stcw.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="/tmp/stcw.pdf",
        storage_type="local",
        classification="certificate",
        extraction_status="approved",
    )
    certification = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="STCW",
        status="valid",
        verification_status="verified",
        document_ref=doc.id,
    )
    db_session.add_all([doc, certification])
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!) {
                    reprocessDocument(documentId: $id) { id extractionStatus }
                }
            """,
            "variables": {"id": doc.id},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["reprocessDocument"]["extractionStatus"] == "pending"

    await db_session.refresh(certification)
    assert certification.document_ref is None
    assert certification.verification_status == "unverified"
    assert certification.status == "pending_verification"


@pytest.mark.asyncio
async def test_reprocess_document_missing_id_errors(client):
    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!) {
                    reprocessDocument(documentId: $id) { id }
                }
            """,
            "variables": {"id": "does-not-exist"},
        },
    )
    body = response.json()
    assert body["data"] is None
    assert "not found" in body["errors"][0]["message"]


@pytest.mark.asyncio
async def test_reprocess_cv_reopens_terminal_review(client, db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="cv.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="/tmp/cv.pdf",
        storage_type="local",
        classification="cv",
        extraction_status="approved",
    )
    db_session.add(doc)
    await db_session.flush()
    review = CVReview(
        document_id=doc.id,
        crew_member_id=crew.id,
        status="approved",
        prior_publication_status="approved",
        proposed_data={"full_name": "Old"},
        approved_data={"full_name": "Old"},
        submitted_by="admin",
        reviewed_by="admin",
        review_note="old decision",
    )
    db_session.add(review)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!) {
                    reprocessDocument(documentId: $id) { id extractionStatus }
                }
            """,
            "variables": {"id": doc.id},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["reprocessDocument"]["extractionStatus"] == "pending"

    await db_session.refresh(review)
    assert review.status == "awaiting_review"
    assert review.proposed_data is None
    assert review.approved_data is None
    assert review.reviewed_by is None


@pytest.mark.asyncio
async def test_reprocess_contractor_document_reopens_incoming_review(client, db_session):
    crew = CrewMember(
        id=str(uuid.uuid4()), full_name="Contractor", role="user", publication_status="approved"
    )
    request = DocumentRequest(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        token_hash="reprocess-review-token",
        expires_at=datetime(2030, 1, 1),
        created_by="admin",
    )
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="certificate.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="/tmp/certificate.pdf",
        storage_type="local",
        classification="certificate",
        extraction_status="approved",
        uploaded_by="contractor-upload-link",
    )
    review = IncomingDocumentReview(
        id=str(uuid.uuid4()),
        request_id=request.id,
        document_id=doc.id,
        status="resolved",
        claimed_by="admin",
        claimed_at=datetime(2026, 9, 1),
        resolved_at=datetime(2026, 9, 1),
    )
    db_session.add_all([crew, request, doc, review])
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": "mutation($id: String!) { reprocessDocument(documentId: $id) { id extractionStatus } }",
            "variables": {"id": doc.id},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["reprocessDocument"]["extractionStatus"] == "pending"

    await db_session.refresh(review)
    assert review.status == "unread"
    assert review.claimed_by is None
    assert review.claimed_at is None
    assert review.resolved_at is None


@pytest.mark.asyncio
async def test_confirm_document_match_rejects_unknown_crew(client, db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Existing Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="certificate.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="/tmp/certificate.pdf",
        storage_type="local",
        classification="certificate",
        extraction_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($documentId: String!, $crewId: String!) {
                    confirmDocumentMatch(documentId: $documentId, crewId: $crewId) { id }
                }
            """,
            "variables": {"documentId": doc.id, "crewId": str(uuid.uuid4())},
        },
    )
    body = response.json()
    assert body["data"] is None
    assert "Crew member not found" in body["errors"][0]["message"]

    await db_session.refresh(doc)
    assert doc.crew_member_id == crew.id


@pytest.mark.asyncio
async def test_confirm_document_match_detaches_old_certificate_projection(client, db_session):
    old_crew = CrewMember(id=str(uuid.uuid4()), full_name="Old Crew", role="user")
    new_crew = CrewMember(id=str(uuid.uuid4()), full_name="New Crew", role="user")
    db_session.add_all([old_crew, new_crew])
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=old_crew.id,
        file_name="certificate.pdf",
        file_type="pdf",
        file_size=10,
        storage_path="/tmp/certificate.pdf",
        storage_type="local",
        classification="certificate",
        extraction_status="extracted",
        extracted_data={"certificate_type": "BOSIET"},
    )
    db_session.add(doc)
    await db_session.flush()
    certification = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=old_crew.id,
        cert_type="bosiet",
        document_ref=doc.id,
        status="valid",
        verification_status="verified",
    )
    db_session.add(certification)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($documentId: String!, $crewId: String!) {
                    confirmDocumentMatch(documentId: $documentId, crewId: $crewId) { id }
                }
            """,
            "variables": {"documentId": doc.id, "crewId": new_crew.id},
        },
    )
    body = response.json()
    assert "errors" not in body, body

    await db_session.refresh(doc)
    await db_session.refresh(certification)
    assert doc.crew_member_id == new_crew.id
    assert certification.document_ref is None
    assert certification.verification_status == "unverified"
    assert certification.status == "pending_verification"


@pytest.mark.asyncio
async def test_update_certification_status(client, db_session):
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Crew",
        role="user",
        medical_expiry=date(2028, 1, 1),
        medical_status="fit",
    )
    db_session.add(crew)
    await db_session.flush()
    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=date(2028, 1, 1),
        status="valid",
        verification_status="verified",
    )
    db_session.add(cert)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!, $status: CertStatus!) {
                    updateCertification(id: $id, status: $status) { id status }
                }
            """,
            "variables": {"id": cert.id, "status": "REJECTED"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["updateCertification"]["status"] == "rejected"
    await db_session.refresh(crew)
    assert crew.medical_expiry is None
    assert crew.medical_status is None


@pytest.mark.asyncio
async def test_update_certification_cannot_mark_unverified_evidence_valid(client, db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Pending Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="BOSIET",
        status="pending_verification",
        verification_status="unverified",
    )
    db_session.add(cert)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!, $status: CertStatus!) {
                    updateCertification(id: $id, status: $status) { status }
                }
            """,
            "variables": {"id": cert.id, "status": "VALID"},
        },
    )

    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["updateCertification"]["status"] == "pending_verification"


@pytest.mark.asyncio
async def test_verify_certification_status(client, db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="huet",
        verification_status="unverified",
        status="pending_verification",
        document_ref="doc-test-123",
    )
    db_session.add(cert)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!, $status: VerificationStatus!) {
                    verifyCertification(id: $id, status: $status) {
                        id
                        status
                        verificationStatus
                        documentRef
                    }
                }
            """,
            "variables": {"id": cert.id, "status": "VERIFIED"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    data = body["data"]["verifyCertification"]
    assert data["verificationStatus"] == "verified"
    assert data["status"] == "valid"
    assert data["documentRef"] == "doc-test-123"

    recheck_response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!, $status: VerificationStatus!) {
                    verifyCertification(id: $id, status: $status) {
                        status
                        verificationStatus
                    }
                }
            """,
            "variables": {"id": cert.id, "status": "UNVERIFIED"},
        },
    )
    recheck_body = recheck_response.json()
    assert "errors" not in recheck_body, recheck_body
    assert recheck_body["data"]["verifyCertification"] == {
        "status": "pending_verification",
        "verificationStatus": "unverified",
    }


@pytest.mark.asyncio
async def test_create_project(client):
    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($clientName: String!, $projectName: String!, $projectType: ProjectType!) {
                    createProject(clientName: $clientName, projectName: $projectName, projectType: $projectType) {
                        id clientName projectName status
                    }
                }
            """,
            "variables": {
                "clientName": "Acme",
                "projectName": "North Sea Survey",
                "projectType": "MARINE_SEISMIC",
            },
        },
    )
    body = response.json()
    assert "errors" not in body, body
    data = body["data"]["createProject"]
    assert data["clientName"] == "Acme"
    assert data["status"] == "planning"


@pytest.mark.asyncio
async def test_update_project_status(client, db_session):
    project = Project(
        id=str(uuid.uuid4()),
        client_name="Client",
        project_name="Project",
        project_type="marine_seismic",
        status="planning",
    )
    db_session.add(project)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!, $status: ProjectStatus!) {
                    updateProject(id: $id, status: $status) { id status }
                }
            """,
            "variables": {"id": project.id, "status": "ACTIVE"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["updateProject"]["status"] == "active"


@pytest.mark.asyncio
async def test_assign_crew_to_project(client, db_session):
    crew_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    project = Project(
        id=str(uuid.uuid4()),
        client_name="Client",
        project_name="Project",
        project_type="environmental",
        status="planning",
    )
    db_session.add(project)
    db_session.add_all(
        [
            CrewMember(id=crew_id, full_name=f"Crew {index}")
            for index, crew_id in enumerate(crew_ids)
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!, $crewIds: [String!]!) {
                    assignCrewToProject(projectId: $id, crewIds: $crewIds) { id }
                }
            """,
            "variables": {"id": project.id, "crewIds": crew_ids},
        },
    )
    body = response.json()
    assert "errors" not in body, body

    await db_session.refresh(project)
    assert project.crew_assigned == crew_ids


@pytest.mark.asyncio
async def test_assign_crew_to_project_rejects_unknown_crew(client, db_session):
    project = Project(
        id=str(uuid.uuid4()),
        client_name="Client",
        project_name="Project",
        project_type="environmental",
        status="planning",
    )
    db_session.add(project)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!, $crewIds: [String!]!) {
                    assignCrewToProject(projectId: $id, crewIds: $crewIds) { id }
                }
            """,
            "variables": {"id": project.id, "crewIds": [str(uuid.uuid4())]},
        },
    )
    body = response.json()
    assert body["data"] is None
    assert "not found" in body["errors"][0]["message"]
