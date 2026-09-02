"""Tests for the AI consultant summary: the profile-open feature built on
top of ConsultantKnowledgeService.summarize(). See
backend/docs/consultant-knowledge-core.md and
backend/docs/cv-ingestion-pipeline.md.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.models import CrewMember


def test_summarize_response_template_formats_without_keyerror():
    """Regression test for a real, previously-undiscovered bug: the
    summarize_response prompt template used {crew_data} as a placeholder,
    but _generate_response only ever passes a `results` kwarg (matching
    every other prompt's convention: {query}/{results}). Every summarize
    call was hitting a KeyError inside the try/except and silently falling
    back to returning raw JSON instead of a generated narrative."""
    from app.services.crew_query import CREW_QUERY_PROMPTS

    formatted = CREW_QUERY_PROMPTS["summarize_response"].format(
        query="Summarize Jane Doe",
        results='{"name": "Jane Doe"}',
        document_data="No documents",
    )
    assert "Jane Doe" in formatted


@pytest.mark.asyncio
async def test_generate_crew_summary_includes_professional_summary(db_session):
    """The LLM must be told the CV's own professional summary explicitly,
    not left to find it buried inside a document's raw extracted_data JSON."""
    from app.services.crew_query import CrewQueryService

    crew = CrewMember(
        full_name="Summary Field Test",
        email="summary-field-test@example.com",
        professional_summary="Experienced offshore surveyor with a strong safety record.",
    )
    db_session.add(crew)
    await db_session.commit()
    await db_session.refresh(crew, attribute_names=["certifications", "work_history", "documents"])

    service = CrewQueryService()
    service._generate_response = AsyncMock(return_value="A generated summary.")

    result = await service.generate_crew_summary(crew)

    assert result == "A generated summary."
    _, _, sent_crew_data_json = service._generate_response.await_args.args
    assert "Experienced offshore surveyor with a strong safety record." in sent_crew_data_json


@pytest.mark.asyncio
async def test_consultant_knowledge_summarize_resolves_by_id_not_fuzzy_name(db_session):
    """Regression test for the redundant/fragile lookup this replaced:
    summarize() used to fetch the crew member by ID just to read
    full_name, then hand that name to a second, fuzzy ILIKE lookup — which
    could match the wrong person if two crew members have overlapping
    names. Two such crew members here prove the by-ID path is unambiguous."""
    from app.services.consultant_knowledge import consultant_knowledge_service

    shorter = CrewMember(full_name="Alex Carter", email="alex.carter@example.com")
    longer = CrewMember(full_name="Alex Carter Jr", email="alex.carter.jr@example.com")
    db_session.add_all([shorter, longer])
    await db_session.commit()

    seen_crew_ids = []

    async def fake_generate(crew):
        seen_crew_ids.append(crew.id)
        return f"Summary for {crew.full_name}"

    with (
        patch(
            "app.services.consultant_knowledge.crew_query_service.generate_crew_summary",
            new=AsyncMock(side_effect=fake_generate),
        ),
        patch.object(
            consultant_knowledge_service, "summarize", wraps=consultant_knowledge_service.summarize
        ),
    ):
        # Bypass the cache wrapper entirely for this assertion by clearing
        # any stale entry first is unnecessary here — a fresh crew_id has
        # never been cached. Call by the *shorter* name's id; a fuzzy
        # ILIKE('%Alex Carter%') would have matched the *longer* one too.
        result = await consultant_knowledge_service.summarize(shorter.id, db_session=db_session)

    assert result == "Summary for Alex Carter"
    assert seen_crew_ids == [shorter.id]


@pytest.mark.asyncio
async def test_summarize_result_is_cached(db_session):
    """First call generates and caches; second call for the same crew_id
    is served from cache without a second LLM call. Uses an in-memory
    fake for cache_service.get/set rather than real Redis, since Redis in
    this dev environment requires a password the host test process isn't
    configured with (a pre-existing, separate environment gap — see
    backend/docs/consultant-knowledge-core.md) — this keeps the test
    hermetic and focused on the caching *logic*, not Redis connectivity."""
    from app.services import cache as cache_module
    from app.services.consultant_knowledge import consultant_knowledge_service

    crew = CrewMember(full_name="Cache Summary Test", email="cache-summary-test@example.com")
    db_session.add(crew)
    await db_session.commit()

    fake_store: dict[str, object] = {}

    async def fake_get(key):
        return fake_store.get(key)

    async def fake_set(key, value, ttl=None):
        fake_store[key] = value
        return True

    with (
        patch.object(cache_module.cache_service, "get", side_effect=fake_get),
        patch.object(cache_module.cache_service, "set", side_effect=fake_set),
        patch(
            "app.services.consultant_knowledge.crew_query_service.generate_crew_summary",
            new=AsyncMock(return_value="A generated summary."),
        ) as mock_generate,
    ):
        first = await consultant_knowledge_service.summarize(crew.id, db_session=db_session)
        second = await consultant_knowledge_service.summarize(crew.id, db_session=db_session)

    assert first == "A generated summary."
    assert second == "A generated summary."
    mock_generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_cv_extraction_invalidates_the_summary_cache():
    """A re-processed CV changes the exact data an AI summary would
    describe — the cached summary must not survive it."""
    import uuid

    from app.database import get_session_factory
    from app.services.cv_processing import cv_processing_service

    factory = get_session_factory()
    crew_id = str(uuid.uuid4())
    async with factory() as session:
        session.add(CrewMember(id=crew_id, full_name="Invalidation Test Crew", role="user"))
        await session.commit()

    from app.services.cache import cache_service

    with patch.object(cache_service, "delete", new=AsyncMock(return_value=True)) as mock_delete:
        await cv_processing_service.process_cv_extraction(
            crew_id, {"nationality": "British"}, str(uuid.uuid4())
        )

    mock_delete.assert_awaited_once_with(cache_service._make_key("summary", crew_id))


@pytest.mark.asyncio
async def test_delete_crew_member_invalidates_summary_and_compliance_cache(client):
    """Regression test for a real bug found via live testing: deleteCrewMember
    removed the crew row and the "crew"/list caches, but never the "summary"
    or "compliance" caches. Both are addressable directly by crew_id via
    crewSummary/complianceStatus regardless of whether the crew record still
    exists, so a stale cache hit kept serving a deleted person's AI summary
    (confirmed live: crewSummary returned the full cached text for a crew_id
    that had already been deleted) and their compliance counts until the
    respective TTL expired. Without the fix, this test fails because
    cache_service.delete is never awaited with the "summary"/"compliance"
    keys."""
    from app.services.cache import cache_service

    create_response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation Create($fullName: String!) {
                    createCrewMember(fullName: $fullName) { id }
                }
            """,
            "variables": {"fullName": "Cache Leak Test Subject"},
        },
    )
    crew_id = create_response.json()["data"]["createCrewMember"]["id"]

    with patch.object(cache_service, "delete", new=AsyncMock(return_value=True)) as mock_delete:
        delete_response = await client.post(
            "/graphql",
            json={
                "query": """
                    mutation Delete($id: String!) {
                        deleteCrewMember(id: $id)
                    }
                """,
                "variables": {"id": crew_id},
            },
        )

    assert delete_response.json()["data"]["deleteCrewMember"] is True
    deleted_keys = [call.args[0] for call in mock_delete.await_args_list]
    assert cache_service._make_key("summary", crew_id) in deleted_keys
    assert cache_service._make_key("compliance", crew_id) in deleted_keys
