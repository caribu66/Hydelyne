"""Test crew member GraphQL operations."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.models import CrewMember, Document
from app.services.crew import crew_service

DELETE_CREW_MUTATION = """
mutation DeleteCrewMember($id: String!) {
    deleteCrewMember(id: $id)
}
"""

CREATE_CREW_MUTATION = """
mutation CreateCrewMember($fullName: String!, $email: String, $phone: String, $nationality: String) {
    createCrewMember(fullName: $fullName, email: $email, phone: $phone, nationality: $nationality) {
        id
        fullName
        email
        phone
        nationality
        availabilityStatus
    }
}
"""

GET_CREW_QUERY = """
query GetCrewMember($id: String!) {
    crewMember(id: $id) {
        id
        fullName
        email
        phone
        nationality
    }
}
"""

LIST_CREW_QUERY = """
query ListCrewMembers {
    crewMembers(limit: 10, offset: 0) {
        id
        fullName
        email
    }
}
"""

UPDATE_CREW_MUTATION = """
mutation UpdateCrewMember($id: String!, $fullName: String, $phone: String) {
    updateCrewMember(id: $id, fullName: $fullName, phone: $phone) {
        id
        fullName
        phone
    }
}
"""

RETIRED_CV_MUTATION = """
mutation UploadCvAndExtract($crewId: String!, $fileName: String!, $fileType: String!, $fileSize: Int!) {
    uploadCvAndExtract(crewId: $crewId, fileName: $fileName, fileType: $fileType, fileSize: $fileSize) {
        documentId
    }
}
"""


@pytest.mark.asyncio
async def test_create_crew_member(client):
    response = await client.post(
        "/graphql",
        json={
            "query": CREATE_CREW_MUTATION,
            "variables": {
                "fullName": "John Smith",
                "email": "john.smith@example.com",
                "phone": "+44 1234 567890",
                "nationality": "British",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]["createCrewMember"]
    assert data["fullName"] == "John Smith"
    assert data["email"] == "john.smith@example.com"
    assert data["availabilityStatus"] == "available"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_get_crew_member(client):
    create_response = await client.post(
        "/graphql",
        json={
            "query": CREATE_CREW_MUTATION,
            "variables": {"fullName": "Jane Doe", "email": "jane@example.com"},
        },
    )
    crew_id = create_response.json()["data"]["createCrewMember"]["id"]

    response = await client.post(
        "/graphql",
        json={"query": GET_CREW_QUERY, "variables": {"id": crew_id}},
    )
    assert response.status_code == 200
    data = response.json()["data"]["crewMember"]
    assert data["fullName"] == "Jane Doe"
    assert data["email"] == "jane@example.com"


@pytest.mark.asyncio
async def test_update_crew_member(client):
    create_response = await client.post(
        "/graphql",
        json={
            "query": CREATE_CREW_MUTATION,
            "variables": {"fullName": "Alex Storm", "email": "alex@example.com"},
        },
    )
    crew_id = create_response.json()["data"]["createCrewMember"]["id"]

    response = await client.post(
        "/graphql",
        json={
            "query": UPDATE_CREW_MUTATION,
            "variables": {"id": crew_id, "fullName": "Alex J. Storm", "phone": "+44 7000 000000"},
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]["updateCrewMember"]
    assert data["fullName"] == "Alex J. Storm"
    assert data["phone"] == "+44 7000 000000"


@pytest.mark.asyncio
async def test_list_crew_members(client):
    response = await client.post(
        "/graphql",
        json={"query": LIST_CREW_QUERY},
    )
    assert response.status_code == 200
    data = response.json()["data"]["crewMembers"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_crew_members_prioritizes_newest_records(db_session):
    older = CrewMember(
        id="crew-older",
        full_name="Older Specialist",
        email="older@example.com",
        created_at=datetime(2026, 1, 1),
    )
    newest = CrewMember(
        id="crew-newest",
        full_name="Newest Specialist",
        email="newest@example.com",
        created_at=datetime(2026, 1, 2),
    )
    db_session.add_all([older, newest])
    await db_session.commit()

    records = await crew_service.list_crew_members(limit=1)

    assert [record.id for record in records] == ["crew-newest"]


@pytest.mark.asyncio
async def test_retired_cv_metadata_mutation_does_not_claim_success(client):
    response = await client.post(
        "/graphql",
        json={
            "query": RETIRED_CV_MUTATION,
            "variables": {
                "crewId": "test-crew-id",
                "fileName": "candidate.pdf",
                "fileType": "application/pdf",
                "fileSize": 42,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] is None
    assert payload["errors"][0]["extensions"]["code"] == "BAD_USER_INPUT"


@pytest.mark.asyncio
async def test_delete_crew_member_retains_everything_when_dropbox_delete_fails(
    client, db_session, monkeypatch
):
    """Characterization test for an invariant that was previously undocumented
    by any test: deleteCrewMember's docstring promises "Dropbox files are
    removed before database metadata so a failed remote deletion leaves the
    member and their documents recoverable." Nothing verified that a failed
    Dropbox delete actually stops the database delete before this test."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Has Dropbox Doc", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="contract.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="/hydenlyne/crew/documents/contract.pdf",
        storage_type="dropbox",
        dropbox_path="/hydenlyne/crew/documents/contract.pdf",
    )
    db_session.add(doc)
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.upload.document_upload_service.delete_from_dropbox",
        AsyncMock(return_value=False),
    )

    response = await client.post(
        "/graphql",
        json={"query": DELETE_CREW_MUTATION, "variables": {"id": crew.id}},
    )
    body = response.json()
    assert body["data"] is None
    assert "errors" in body

    still_there = await crew_service.get_crew_member(crew.id)
    assert still_there is not None
    assert len(still_there.documents) == 1


@pytest.mark.asyncio
async def test_admin_cannot_delete_own_account(client):
    """Characterization test: the resolver has an explicit self-delete guard
    with zero prior test coverage. conftest.py's default test identity has a
    fixed id, so this deletes that exact id to hit the guard."""
    from tests.conftest import _dummy_user

    response = await client.post(
        "/graphql",
        json={"query": DELETE_CREW_MUTATION, "variables": {"id": _dummy_user.id}},
    )
    body = response.json()
    assert body["data"] is None
    assert "cannot delete your own administrator account" in body["errors"][0]["message"]
