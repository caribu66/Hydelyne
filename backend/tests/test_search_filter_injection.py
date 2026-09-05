"""Security regression tests: Meilisearch filter-injection via /api/search/*.

Before this fix, `availability`, `classification`, and `crew_id` query params
were spliced unescaped into Meilisearch filter strings (e.g.
`f'availability_status = "{availability}"'`). A value containing `"` could
break out of the intended clause and inject arbitrary filter syntax (a
`""` or ` OR ` payload could turn a "filter to my availability" query into
"return everything" or an arbitrarily scoped read). Fixed by allowlisting
against the canonical `app/domain/fields.py` enums and validating `crew_id`
as a UUID before it reaches the filter string.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.meilisearch import meilisearch_client


@pytest.mark.asyncio
async def test_search_crew_rejects_injection_in_availability(client):
    response = await client.get(
        "/api/search/crew", params={"q": "smith", "availability": '" OR "1"="1'}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_crew_accepts_valid_availability(client):
    with patch.object(
        meilisearch_client,
        "search_crew_members",
        AsyncMock(return_value={"hits": []}),
    ) as mocked:
        response = await client.get(
            "/api/search/crew", params={"q": "smith", "availability": "available"}
        )
        assert response.status_code == 200
        _, kwargs = mocked.call_args
        assert kwargs["filters"] == 'availability_status = "available"'


@pytest.mark.asyncio
async def test_search_documents_rejects_injection_in_classification(client):
    response = await client.get(
        "/api/search/documents", params={"q": "passport", "classification": '"; DROP'}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_documents_rejects_injection_in_crew_id(client):
    response = await client.get(
        "/api/search/documents", params={"q": "passport", "crew_id": '" OR "1"="1'}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_documents_accepts_valid_filters(client):
    with patch.object(
        meilisearch_client,
        "search_documents",
        AsyncMock(return_value={"hits": []}),
    ) as mocked:
        crew_id = "9d5f4e2a-6b3c-4a1d-8f2e-1c9b7a3d5e6f"
        response = await client.get(
            "/api/search/documents",
            params={"q": "passport", "classification": "identity", "crew_id": crew_id},
        )
        assert response.status_code == 200
        _, kwargs = mocked.call_args
        assert kwargs["filters"] == f'classification = "identity" AND crew_member_id = "{crew_id}"'
