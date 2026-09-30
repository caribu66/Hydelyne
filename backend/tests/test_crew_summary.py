"""Tests for the AI consultant summary: the profile-open feature built on
top of ConsultantKnowledgeService.summarize(). See
backend/docs/consultant-knowledge-core.md and
backend/docs/cv-ingestion-pipeline.md.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models import CrewMember


def _mock_user(monkeypatch, role, user_id=None):
    from app.services.crew import auth_service

    user = CrewMember(
        id=user_id or str(uuid.uuid4()),
        full_name=f"{role.title()} User",
        email=f"{role}-summary@test.com",
        role=role,
    )
    monkeypatch.setattr(auth_service, "get_user_from_token", AsyncMock(return_value=user))
    return user


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
async def test_generate_crew_summary_excludes_private_and_document_data(db_session):
    """The authenticated summary surface must not turn C2/C3 fields into prose.

    GraphQL field scrubbing cannot redact values after an LLM has incorporated
    them into a returned string, so the prompt itself must be C1-safe.
    """
    from datetime import date

    from app.models import Document
    from app.services.crew_query import CrewQueryService

    crew = CrewMember(
        full_name="Summary Privacy Test",
        email="private@example.com",
        phone="+44 7000 999999",
        medical_expiry=date(2030, 1, 1),
        passport_expiry=date(2031, 1, 1),
    )
    db_session.add(crew)
    await db_session.flush()
    db_session.add(
        Document(
            crew_member_id=crew.id,
            file_name="passport.pdf",
            file_type="pdf",
            file_size=10,
            storage_type="local",
            storage_path="/tmp/passport.pdf",
            classification="passport",
            extracted_data={"passport_number": "P-SECRET-123"},
        )
    )
    await db_session.commit()
    await db_session.refresh(crew, attribute_names=["certifications", "work_history", "documents"])

    service = CrewQueryService()
    service._generate_response = AsyncMock(return_value="A generated summary.")

    await service.generate_crew_summary(crew)
    sent_crew_data_json = service._generate_response.await_args.args[2]
    sent_document_data_json = service._generate_response.await_args.kwargs["document_data"]

    for private_value in ("private@example.com", "+44 7000 999999", "2030-01-01", "2031-01-01"):
        assert private_value not in sent_crew_data_json
    assert "P-SECRET-123" not in sent_document_data_json
    assert "passport.pdf" not in sent_document_data_json
    assert "passport" not in sent_document_data_json


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
async def test_summary_cache_cannot_bypass_publication_revocation(db_session):
    """A stale Redis summary must not survive profile demotion or deletion."""
    from app.services import cache as cache_module
    from app.services.consultant_knowledge import consultant_knowledge_service

    crew = CrewMember(full_name="Revoked Summary Test", publication_status="rejected")
    db_session.add(crew)
    await db_session.commit()

    with (
        patch.object(
            cache_module.cache_service,
            "get",
            new=AsyncMock(return_value="stale private profile summary"),
        ),
        patch(
            "app.services.consultant_knowledge.crew_query_service.generate_crew_summary",
            new=AsyncMock(),
        ) as mock_generate,
    ):
        result = await consultant_knowledge_service.summarize(crew.id, db_session=db_session)

    assert result == "No crew member found with that id."
    mock_generate.assert_not_awaited()


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
async def test_crew_summary_denies_t1_enumeration(client, db_session, monkeypatch):
    """Any authenticated T1 caller could previously enumerate crew_summary by
    ID (one Ollama/cache call per ID). T1 now gets the same not-found string
    as a missing profile, and generation is never invoked."""
    _mock_user(monkeypatch, "user")
    target = CrewMember(
        full_name="Enumerated Contractor",
        email="enumerated@example.com",
        publication_status="approved",
    )
    db_session.add(target)
    await db_session.commit()

    with patch(
        "app.services.consultant_knowledge.crew_query_service.generate_crew_summary",
        new=AsyncMock(return_value="A generated summary."),
    ) as mock_generate:
        response = await client.post(
            "/graphql",
            json={
                "query": "query($id: String!) { crewSummary(crewId: $id) }",
                "variables": {"id": target.id},
            },
        )

    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["crewSummary"] == "No crew member found with that id."
    mock_generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_crew_summary_denies_other_users_draft(client, db_session, monkeypatch):
    """Drafts are visible only to their submitter and administrators: another
    authenticated user must not obtain a draft's summary."""
    owner_id = str(uuid.uuid4())
    _mock_user(monkeypatch, "user")
    draft = CrewMember(
        full_name="Someone Elses Draft",
        email="someone-elses-draft@example.com",
        publication_status="draft",
        submitted_by=owner_id,
    )
    db_session.add(draft)
    await db_session.commit()

    with patch(
        "app.services.consultant_knowledge.crew_query_service.generate_crew_summary",
        new=AsyncMock(return_value="A generated summary."),
    ) as mock_generate:
        response = await client.post(
            "/graphql",
            json={
                "query": "query($id: String!) { crewSummary(crewId: $id) }",
                "variables": {"id": draft.id},
            },
        )

    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["crewSummary"] == "No crew member found with that id."
    mock_generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_crew_summary_allows_staff_for_approved_profile(client, db_session, monkeypatch):
    """Staff (T2) with profile access still receive the authorized summary."""
    _mock_user(monkeypatch, "staff")
    target = CrewMember(
        full_name="Approved Contractor",
        email="approved-summary@example.com",
        publication_status="approved",
    )
    db_session.add(target)
    await db_session.commit()

    with patch(
        "app.services.consultant_knowledge.crew_query_service.generate_crew_summary",
        new=AsyncMock(return_value="A generated summary."),
    ):
        response = await client.post(
            "/graphql",
            json={
                "query": "query($id: String!) { crewSummary(crewId: $id) }",
                "variables": {"id": target.id},
            },
        )

    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["crewSummary"] == "A generated summary."


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
