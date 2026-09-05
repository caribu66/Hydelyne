"""Regression tests for the Meilisearch index-sync fix.

Before this fix, `createCrewMember`/`updateCrewMember` never touched the
Meilisearch index (only `deleteCrewMember` did), so the index silently went
stale after every crew edit. See backend/docs/consultant-knowledge-core.md.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.meilisearch import meilisearch_client

CREATE_CREW_MUTATION = """
mutation CreateCrewMember($fullName: String!, $email: String) {
    createCrewMember(fullName: $fullName, email: $email) {
        id
        fullName
    }
}
"""

UPDATE_CREW_MUTATION = """
mutation UpdateCrewMember($id: String!, $fullName: String) {
    updateCrewMember(id: $id, fullName: $fullName) {
        id
        fullName
    }
}
"""


@pytest.mark.asyncio
async def test_create_crew_member_syncs_meilisearch_index(client):
    meilisearch_client.index_crew_member.reset_mock()

    response = await client.post(
        "/graphql",
        json={
            "query": CREATE_CREW_MUTATION,
            "variables": {"fullName": "Priya Anand", "email": "priya@example.com"},
        },
    )
    assert response.status_code == 200
    crew_id = response.json()["data"]["createCrewMember"]["id"]

    meilisearch_client.index_crew_member.assert_awaited_once()
    (indexed_doc,), _ = meilisearch_client.index_crew_member.call_args
    assert indexed_doc["id"] == crew_id
    assert indexed_doc["full_name"] == "Priya Anand"
    assert indexed_doc["email"] == "priya@example.com"
    assert indexed_doc["publication_status"] == "approved"


@pytest.mark.asyncio
async def test_update_crew_member_syncs_meilisearch_index(client):
    create_response = await client.post(
        "/graphql",
        json={
            "query": CREATE_CREW_MUTATION,
            "variables": {"fullName": "Sam Okafor", "email": "sam@example.com"},
        },
    )
    crew_id = create_response.json()["data"]["createCrewMember"]["id"]

    meilisearch_client.index_crew_member.reset_mock()

    response = await client.post(
        "/graphql",
        json={
            "query": UPDATE_CREW_MUTATION,
            "variables": {"id": crew_id, "fullName": "Samuel Okafor"},
        },
    )
    assert response.status_code == 200

    meilisearch_client.index_crew_member.assert_awaited_once()
    (indexed_doc,), _ = meilisearch_client.index_crew_member.call_args
    assert indexed_doc["id"] == crew_id
    assert indexed_doc["full_name"] == "Samuel Okafor"


@pytest.mark.asyncio
async def test_keyword_search_always_filters_to_approved_contractors():
    fake_index = MagicMock()
    fake_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    fake_client = MagicMock()
    fake_client.index.return_value = fake_index

    with patch.object(meilisearch_client, "_client", fake_client):
        await meilisearch_client.search_crew_members(
            "medic", filters='availability_status = "available"'
        )

    args, _ = fake_index.search.call_args
    search_params = args[1]
    assert search_params["filter"] == (
        'publication_status = "approved" AND availability_status = "available"'
    )
