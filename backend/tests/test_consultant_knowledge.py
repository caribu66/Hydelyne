"""Tests for the Phase 2 core: ConsultantKnowledgeService, the single access
layer future features should call instead of reaching into Postgres/
Meilisearch/Qdrant/Ollama directly. See backend/docs/consultant-knowledge-core.md.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import get_session_factory
from app.models import Certification, CrewMember, Document, WorkHistory
from app.services.consultant_knowledge import consultant_knowledge_service, qdrant_service


async def _create_crew_with_relations(session) -> str:
    crew_id = str(uuid.uuid4())
    session.add(
        CrewMember(
            id=crew_id,
            full_name="Knowledge Core Test Crew",
            email="knowledge-core@example.com",
            role="user",
        )
    )
    session.add(
        Certification(
            id=str(uuid.uuid4()),
            crew_member_id=crew_id,
            cert_type="BOSIET",
            status="valid",
        )
    )
    session.add(
        WorkHistory(
            id=str(uuid.uuid4()),
            crew_member_id=crew_id,
            client_name="Acme Offshore",
            role="Surveyor",
        )
    )
    session.add(
        Document(
            id=str(uuid.uuid4()),
            crew_member_id=crew_id,
            file_name="cv.pdf",
            file_type="pdf",
            file_size=1024,
            storage_type="local",
            storage_path="/tmp/cv.pdf",
            classification="cv",
            extraction_status="extracted",
        )
    )
    await session.commit()
    return crew_id


@pytest.mark.asyncio
async def test_get_profile_returns_crew_certifications_work_history_and_documents():
    factory = get_session_factory()
    async with factory() as session:
        crew_id = await _create_crew_with_relations(session)

    async with factory() as session:
        profile = await consultant_knowledge_service.get_profile(crew_id, db_session=session)

    assert profile is not None
    assert profile.crew_member.id == crew_id
    assert profile.crew_member.full_name == "Knowledge Core Test Crew"
    assert len(profile.crew_member.certifications) == 1
    assert profile.crew_member.certifications[0].cert_type == "BOSIET"
    assert len(profile.crew_member.work_history) == 1
    assert profile.crew_member.work_history[0].client_name == "Acme Offshore"
    assert len(profile.documents) == 1
    assert profile.documents[0].file_name == "cv.pdf"
    assert profile.documents[0].classification == "cv"


@pytest.mark.asyncio
async def test_get_profile_returns_none_for_unknown_crew_id():
    factory = get_session_factory()
    async with factory() as session:
        profile = await consultant_knowledge_service.get_profile(
            str(uuid.uuid4()), db_session=session
        )

    assert profile is None


@pytest.mark.asyncio
async def test_summarize_returns_graceful_message_for_unknown_crew_id():
    """The not-found branch returns without ever calling Ollama, so this
    stays a fast, always-run test; the LLM-backed narrative branch is
    exercised manually/under `pytest -m llm` alongside crew_query.py's own
    Ollama-dependent tests."""
    factory = get_session_factory()
    async with factory() as session:
        summary = await consultant_knowledge_service.summarize(
            str(uuid.uuid4()), db_session=session
        )

    assert "No crew member found" in summary


@pytest.mark.asyncio
async def test_semantic_search_mode_is_disabled_by_default():
    """Documents the Phase 3 checkpoint: the code is wired, but stays
    inert (raises rather than silently degrading) until
    ENABLE_SEMANTIC_SEARCH is explicitly turned on."""
    settings = get_settings()
    assert settings.ENABLE_SEMANTIC_SEARCH is False

    factory = get_session_factory()
    async with factory() as session:
        with pytest.raises(NotImplementedError):
            await consultant_knowledge_service.search(
                "anything", db_session=session, mode="semantic"
            )


@pytest.mark.asyncio
async def test_semantic_search_activates_once_flag_is_enabled():
    """When ENABLE_SEMANTIC_SEARCH is on, search(mode="semantic") actually
    calls Qdrant instead of raising — proving the gate itself is wired
    correctly, not just the off-path stub."""
    settings = get_settings()
    factory = get_session_factory()
    fake_hits = [{"id": "doc-1", "score": 0.91, "metadata": {"file_name": "cv.pdf"}}]

    with patch.object(
        qdrant_service, "search_similar", new=AsyncMock(return_value=fake_hits)
    ) as mock_search:
        settings.ENABLE_SEMANTIC_SEARCH = True
        try:
            async with factory() as session:
                result = await consultant_knowledge_service.search(
                    "offshore wind survey experience", db_session=session, mode="semantic"
                )
        finally:
            settings.ENABLE_SEMANTIC_SEARCH = False

    mock_search.assert_awaited_once()
    assert result.mode == "semantic"
    assert result.results == fake_hits


@pytest.mark.asyncio
async def test_similar_documents_is_a_phase_3_gated_stub_until_enabled():
    factory = get_session_factory()
    async with factory() as session:
        crew_id = await _create_crew_with_relations(session)
        result = await session.execute(select(Document).where(Document.crew_member_id == crew_id))
        document_id = result.scalar_one().id

    async with factory() as session:
        # Off by default: no Qdrant call at all.
        assert (
            await consultant_knowledge_service.similar_documents(document_id, db_session=session)
            == []
        )

    settings = get_settings()
    fake_hits = [
        {"id": document_id, "score": 1.0, "metadata": {}},  # the document itself
        {"id": "other-doc", "score": 0.8, "metadata": {}},
    ]
    with patch.object(qdrant_service, "search_similar", new=AsyncMock(return_value=fake_hits)):
        settings.ENABLE_SEMANTIC_SEARCH = True
        try:
            async with factory() as session:
                results = await consultant_knowledge_service.similar_documents(
                    document_id, db_session=session
                )
        finally:
            settings.ENABLE_SEMANTIC_SEARCH = False

    # The source document is excluded from its own "similar" results.
    assert results == [{"id": "other-doc", "score": 0.8, "metadata": {}}]
