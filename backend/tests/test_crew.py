"""Test crew member GraphQL operations."""

from datetime import datetime

import pytest

from app.models import CrewMember
from app.services.crew import crew_service

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
