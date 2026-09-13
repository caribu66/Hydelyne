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

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models import CrewMember
from app.services.meilisearch import SearchProviderUnavailable, meilisearch_client


class _SearchSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


class _SearchResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


@pytest.mark.asyncio
async def test_manual_index_reports_login_account_as_excluded(monkeypatch):
    from app.api.search import index_crew_member
    from app.services.consultant_knowledge import consultant_knowledge_service

    account = SimpleNamespace(
        id="staff-1",
        publication_status="approved",
        password_hash="stored-password-hash",
        role="staff",
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=_SearchResult(account)))
    monkeypatch.setattr(
        "app.database.get_session_factory",
        lambda: lambda: _SearchSessionContext(session),
    )
    monkeypatch.setattr(
        consultant_knowledge_service,
        "index_crew_member",
        AsyncMock(return_value=True),
    )

    result = await index_crew_member("staff-1", None, account)

    assert result == {"status": "excluded"}


@pytest.mark.asyncio
async def test_search_crew_rejects_injection_in_availability(client):
    response = await client.get(
        "/api/search/crew", params={"q": "smith", "availability": '" OR "1"="1'}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/search/crew", "/api/search/documents"])
@pytest.mark.parametrize("query", ["   ", "x" * 501])
async def test_search_rejects_blank_or_oversized_query(client, path, query):
    response = await client.get(path, params={"q": query})
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
        assert kwargs["filters"] == (
            'publication_status = "approved" AND availability_status = "available"'
        )


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
@pytest.mark.parametrize(
    "params",
    [
        {"classification": '" OR "1"="1'},
        {"crew_id": '" OR "1"="1'},
    ],
)
async def test_search_documents_validates_filters_before_empty_staff_scope(
    client, monkeypatch, params
):
    """Malformed filters must not become an empty success for staff with no visible profiles."""
    from app.services.crew import auth_service

    monkeypatch.setattr(
        auth_service,
        "get_user_from_token",
        AsyncMock(
            return_value=CrewMember(
                id=str(uuid.uuid4()),
                full_name="Staff Search User",
                role="staff",
            )
        ),
    )
    response = await client.get("/api/search/documents", params={"q": "passport", **params})
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
        assert kwargs["filters"] == (
            f'extraction_status IN ["approved", "extracted"] AND classification = "identity" '
            f'AND crew_member_id = "{crew_id}"'
        )


@pytest.mark.asyncio
async def test_search_documents_normalizes_upload_classification_alias(client):
    """Search accepts the same legacy aliases as document upload."""
    with patch.object(
        meilisearch_client,
        "search_documents",
        AsyncMock(return_value={"hits": []}),
    ) as mocked:
        response = await client.get(
            "/api/search/documents",
            params={"q": "certificate", "classification": " CERT "},
        )

    assert response.status_code == 200
    _, kwargs = mocked.call_args
    assert 'classification = "certificate"' in kwargs["filters"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "method_name"),
    [("/api/search/crew", "search_crew_members"), ("/api/search/documents", "search_documents")],
)
async def test_search_provider_failure_is_not_reported_as_empty_success(
    client, path, method_name
):
    with patch.object(
        meilisearch_client,
        method_name,
        AsyncMock(side_effect=SearchProviderUnavailable("provider down")),
    ):
        response = await client.get(path, params={"q": "passport"})

    assert response.status_code == 503
    assert response.json()["detail"].endswith("temporarily unavailable")


@pytest.mark.asyncio
async def test_search_documents_excludes_unapproved_extractions(client):
    with patch.object(
        meilisearch_client,
        "search_documents",
        AsyncMock(return_value={"hits": []}),
    ) as mocked:
        response = await client.get("/api/search/documents", params={"q": "cv"})

    assert response.status_code == 200
    _, kwargs = mocked.call_args
    assert kwargs["filters"] == 'extraction_status IN ["approved", "extracted"]'


@pytest.mark.asyncio
async def test_search_documents_drops_projection_hits_without_source_ids(client):
    with patch.object(
        meilisearch_client,
        "search_documents",
        AsyncMock(
            return_value={
                "hits": [
                    "malformed-hit",
                    {
                        "extracted_data": {"passport": "stale-secret"},
                        "extracted_text": "stale raw document text",
                    },
                ],
                "estimated_total_hits": 1,
            }
        ),
    ):
        response = await client.get("/api/search/documents?q=passport")

    assert response.status_code == 200
    assert response.json()["hits"] == []


@pytest.mark.asyncio
async def test_search_crew_reapplies_availability_from_source_of_truth(client, db_session):
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Current Unavailable Name",
        availability_status="unavailable",
        publication_status="approved",
    )
    db_session.add(crew)
    await db_session.commit()

    with patch.object(
        meilisearch_client,
        "search_crew_members",
        AsyncMock(
            return_value={
                "hits": [
                    {
                        "id": crew.id,
                        "full_name": "Stale Available Name",
                        "availability_status": "available",
                    }
                ]
            }
        ),
    ):
        response = await client.get(
            "/api/search/crew", params={"q": "name", "availability": "available"}
        )

    assert response.status_code == 200
    assert response.json()["hits"] == []


@pytest.mark.asyncio
async def test_search_crew_rehydrates_current_profile_fields(client, db_session):
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Current Name",
        nationality="Current Nationality",
        publication_status="approved",
    )
    db_session.add(crew)
    await db_session.commit()

    with patch.object(
        meilisearch_client,
        "search_crew_members",
        AsyncMock(return_value={"hits": [{"id": crew.id, "full_name": "Stale Name"}]}),
    ):
        response = await client.get("/api/search/crew", params={"q": "name"})

    assert response.status_code == 200
    assert response.json()["hits"][0]["full_name"] == "Current Name"
    assert response.json()["hits"][0]["nationality"] == "Current Nationality"


@pytest.mark.asyncio
async def test_search_crew_drops_stale_login_account_projection(client, db_session):
    """A stale approved account hit must not cross the PostgreSQL boundary."""
    account = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Operations Account",
        role="staff",
        password_hash="stored-password-hash",
        publication_status="approved",
    )
    db_session.add(account)
    await db_session.commit()

    with patch.object(
        meilisearch_client,
        "search_crew_members",
        AsyncMock(return_value={"hits": [{"id": account.id, "full_name": account.full_name}]}),
    ):
        response = await client.get("/api/search/crew", params={"q": "operations"})

    assert response.status_code == 200
    assert response.json()["hits"] == []
