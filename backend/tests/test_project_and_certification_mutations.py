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

import pytest

from app.models import Certification, CrewMember, Document, Project


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
async def test_update_certification_status(client, db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="bosiet",
        status="pending_verification",
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
            "variables": {"id": cert.id, "status": "VALID"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["updateCertification"]["status"] == "valid"


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
    )
    db_session.add(cert)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation($id: String!, $status: VerificationStatus!) {
                    verifyCertification(id: $id, status: $status) { id verificationStatus }
                }
            """,
            "variables": {"id": cert.id, "status": "VERIFIED"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["verifyCertification"]["verificationStatus"] == "verified"


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
            "variables": {"id": project.id, "crewIds": ["crew-1", "crew-2"]},
        },
    )
    body = response.json()
    assert "errors" not in body, body

    await db_session.refresh(project)
    assert project.crew_assigned == ["crew-1", "crew-2"]
