"""Characterization tests for the project/documentsByCrew GraphQL queries.

Written before extracting their inline SQLAlchemy queries out of
app/graphql/schema.py and into app/services/project.py and
app/services/document_service.py (see docs/AUDIT_2026-09-02.md P2 #9/#10 —
"GraphQL schema ... contain direct database orchestration"). These lock in
current behavior so the extraction can be verified as a pure move, not a
rewrite.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.models import CrewMember, Document, Project


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


@pytest.mark.asyncio
async def test_project_returns_project_by_id(client, db_session, monkeypatch):
    _mock_admin_user(monkeypatch)
    project = Project(
        id=str(uuid.uuid4()),
        client_name="Acme Subsea",
        project_name="North Sea Survey",
        project_type="marine_seismic",
        location="North Sea",
        country="UK",
        status="active",
    )
    db_session.add(project)
    await db_session.commit()

    response = await client.post(
        "/graphql",
        headers=_admin_headers(),
        json={
            "query": """
                query($id: String!) {
                    project(id: $id) { id clientName projectName status }
                }
            """,
            "variables": {"id": project.id},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    data = body["data"]["project"]
    assert data["id"] == project.id
    assert data["clientName"] == "Acme Subsea"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_project_returns_none_for_missing_id(client, monkeypatch):
    _mock_admin_user(monkeypatch)

    response = await client.post(
        "/graphql",
        headers=_admin_headers(),
        json={"query": 'query { project(id: "does-not-exist") { id } }'},
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["project"] is None


@pytest.mark.asyncio
async def test_projects_filters_by_status(client, db_session, monkeypatch):
    _mock_admin_user(monkeypatch)
    active = Project(
        id=str(uuid.uuid4()),
        client_name="Client A",
        project_name="Active Job",
        project_type="marine_seismic",
        status="active",
    )
    planning = Project(
        id=str(uuid.uuid4()),
        client_name="Client B",
        project_name="Planning Job",
        project_type="environmental",
        status="planning",
    )
    db_session.add_all([active, planning])
    await db_session.commit()

    response = await client.post(
        "/graphql",
        headers=_admin_headers(),
        json={"query": "query { projects(status: ACTIVE) { id status } }"},
    )
    body = response.json()
    assert "errors" not in body, body
    ids = [p["id"] for p in body["data"]["projects"]]
    assert active.id in ids
    assert planning.id not in ids


@pytest.mark.asyncio
async def test_documents_by_crew_returns_only_that_crews_documents(client, db_session, monkeypatch):
    _mock_admin_user(monkeypatch)
    crew_a = CrewMember(id=str(uuid.uuid4()), full_name="Crew A", role="user")
    crew_b = CrewMember(id=str(uuid.uuid4()), full_name="Crew B", role="user")
    db_session.add_all([crew_a, crew_b])
    await db_session.flush()

    doc_a = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew_a.id,
        file_name="a.pdf",
        file_type="application/pdf",
        file_size=100,
        storage_path="/tmp/a.pdf",
        storage_type="local",
    )
    doc_b = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew_b.id,
        file_name="b.pdf",
        file_type="application/pdf",
        file_size=100,
        storage_path="/tmp/b.pdf",
        storage_type="local",
    )
    db_session.add_all([doc_a, doc_b])
    await db_session.commit()

    response = await client.post(
        "/graphql",
        headers=_admin_headers(),
        json={
            "query": """
                query($crewId: String!) {
                    documentsByCrew(crewId: $crewId) { id fileName }
                }
            """,
            "variables": {"crewId": crew_a.id},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    docs = body["data"]["documentsByCrew"]
    assert len(docs) == 1
    assert docs[0]["id"] == doc_a.id
