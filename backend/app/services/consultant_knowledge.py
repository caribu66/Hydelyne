"""The single access-layer service for consultant/crew knowledge.

Any future feature (search UI, summaries, agent tool-calling, reports) should
call this service instead of reaching into Postgres, Meilisearch, Qdrant, or
Ollama directly and reimplementing intent logic. See
backend/docs/consultant-knowledge-core.md for the reasoning behind this and
the phase this module is part of.

This is a Phase 2 refactor, not a rewrite: `search(mode="structured"/"auto")`
delegates to the existing, unmodified `CrewQueryService` — the one retrieval
path already proven in production — rather than reimplementing it.
`similar_documents`/`search(mode="semantic")` are Phase-3-gated stubs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import CrewMember, Document
from app.services.crew_query import crew_query_service
from app.services.meilisearch import meilisearch_client
from app.services.qdrant import document_indexable_text, qdrant_service

logger = logging.getLogger(__name__)


@dataclass
class DocumentSummary:
    id: str
    file_name: str
    classification: Optional[str]
    extraction_status: str


@dataclass
class ConsultantProfile:
    """Everything about one consultant in a single call: the crew member row
    (certifications/work_history eager-loaded) plus a lightweight summary of
    their linked documents — one round trip instead of several ad hoc joins."""

    crew_member: CrewMember
    documents: list[DocumentSummary] = field(default_factory=list)


@dataclass
class SearchResult:
    mode: str
    intent: Optional[str] = None
    summary: Optional[str] = None
    results: list[dict[str, Any]] = field(default_factory=list)
    criteria: Optional[dict[str, Any]] = None
    total_issues: Optional[int] = None
    crew_id: Optional[str] = None
    crew_name: Optional[str] = None
    # The unmodified dict a delegated backend returned, kept around so
    # existing callers (e.g. the GraphQL resolver) can migrate without any
    # change in the shape of data they read.
    raw: Optional[dict[str, Any]] = None


def _crew_meilisearch_doc(crew: CrewMember) -> dict:
    """Build the Meilisearch crew document. Mirrors app/api/search.py's
    manual-reindex endpoint so every call site indexes the same shape."""
    return {
        "id": crew.id,
        "full_name": crew.full_name,
        "email": crew.email,
        "phone": crew.phone,
        "nationality": crew.nationality,
        "availability_status": crew.availability_status,
        "tags": crew.tags or [],
    }


class ConsultantKnowledgeService:
    """One door onto consultant/crew data: structured DB and keyword search
    today, semantic search once Phase 3 validates it — plus write-path index
    sync, so a new field/entity can't repeat the Meilisearch staleness bug."""

    async def get_profile(
        self, crew_id: str, *, db_session: AsyncSession
    ) -> Optional[ConsultantProfile]:
        stmt = (
            select(CrewMember)
            .options(
                selectinload(CrewMember.certifications),
                selectinload(CrewMember.work_history),
            )
            .where(CrewMember.id == crew_id)
        )
        crew_member = (await db_session.execute(stmt)).scalar_one_or_none()
        if crew_member is None:
            return None

        doc_stmt = select(Document).where(Document.crew_member_id == crew_id)
        documents = (await db_session.execute(doc_stmt)).scalars().all()
        doc_summaries = [
            DocumentSummary(
                id=d.id,
                file_name=d.file_name,
                classification=d.classification,
                extraction_status=d.extraction_status,
            )
            for d in documents
        ]
        return ConsultantProfile(crew_member=crew_member, documents=doc_summaries)

    async def search(
        self,
        query: str,
        *,
        db_session: AsyncSession,
        mode: Literal["auto", "structured", "keyword", "semantic"] = "auto",
    ) -> SearchResult:
        """Natural-language or structured crew search.

        mode="structured"/"auto" delegates to CrewQueryService.process_query
        (direct-SQL filters + Ollama intent classification + Ollama summary),
        unchanged from before this refactor. mode="keyword" delegates to
        Meilisearch. mode="semantic" delegates to Qdrant but is gated behind
        settings.ENABLE_SEMANTIC_SEARCH (default off) — see the Phase 3
        checkpoint in backend/docs/consultant-knowledge-core.md: the code is
        wired, but stays inert until that validation earns it a default-on
        switch, so existing callers see no behavior change.
        """
        if mode in ("auto", "structured"):
            raw = await crew_query_service.process_query(query, db_session)
            return SearchResult(
                mode="structured",
                intent=raw.get("intent"),
                summary=raw.get("summary"),
                results=raw.get("results") or [],
                criteria=raw.get("criteria"),
                total_issues=raw.get("total_issues"),
                crew_id=raw.get("crew_id"),
                crew_name=raw.get("crew_name"),
                raw=raw,
            )
        if mode == "keyword":
            raw = await meilisearch_client.search_crew_members(query)
            return SearchResult(mode="keyword", results=raw.get("hits", []), raw=raw)

        # mode == "semantic"
        if not get_settings().ENABLE_SEMANTIC_SEARCH:
            raise NotImplementedError(
                "Semantic search is implemented but not enabled. It stays off "
                "until the Phase 3 validation in "
                "backend/docs/consultant-knowledge-core.md justifies turning "
                "on ENABLE_SEMANTIC_SEARCH."
            )
        hits = await qdrant_service.search_similar(query, limit=20)
        return SearchResult(mode="semantic", results=hits, raw={"hits": hits})

    async def summarize(self, crew_id: str, *, db_session: AsyncSession) -> str:
        """A short natural-language summary of one consultant, reusing the
        same summary-building/generation crew_query.py already has, rather
        than a second, independent summarization prompt.

        Fetches the crew member once, directly by ID — unlike the
        NL-search "summarize X" path (crew_query.py::_handle_summarize),
        which only has a parsed name and must fuzzy-match it, this call
        already has the exact ID, so there's no second lookup and no
        risk of matching the wrong person with a similar name.

        Cached (see app/services/cache.py::SUMMARY_TTL) since this is
        shown automatically whenever a profile is opened — the first view
        pays for the Ollama call, every view after that until the profile
        changes is instant. Invalidated in the crew-update mutation and
        after CV re-processing (see backend/docs/consultant-knowledge-core.md).
        """
        from app.services.cache import cache_service

        cache_key = cache_service._make_key("summary", crew_id)

        async def _generate() -> str:
            stmt = (
                select(CrewMember)
                .options(
                    selectinload(CrewMember.certifications),
                    selectinload(CrewMember.work_history),
                    selectinload(CrewMember.documents),
                )
                .where(CrewMember.id == crew_id)
            )
            crew_member = (await db_session.execute(stmt)).scalar_one_or_none()
            if crew_member is None:
                return "No crew member found with that id."
            return await crew_query_service.generate_crew_summary(crew_member)

        return await cache_service.get_or_set(cache_key, _generate, ttl=cache_service.SUMMARY_TTL)

    async def similar_documents(
        self, document_id: str, *, db_session: AsyncSession, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Documents whose content is semantically similar to the given one.

        Gated behind settings.ENABLE_SEMANTIC_SEARCH (Phase 3 checkpoint in
        backend/docs/consultant-knowledge-core.md) — returns [] while the
        flag is off, so existing callers see no behavior change by default.
        """
        if not get_settings().ENABLE_SEMANTIC_SEARCH:
            return []

        document = (
            await db_session.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if document is None:
            return []

        hits = await qdrant_service.search_similar(
            document_indexable_text(document), limit=limit + 1
        )
        return [hit for hit in hits if hit.get("id") != document_id][:limit]

    async def index_crew_member(self, crew: CrewMember) -> None:
        """Keep Meilisearch in sync. Called from create/update mutations —
        centralized here so the next new field/entity can't forget it again
        the way createCrewMember/updateCrewMember did before this fix."""
        await meilisearch_client.index_crew_member(_crew_meilisearch_doc(crew))

    async def remove_from_index(self, crew_id: str) -> None:
        await meilisearch_client.delete_crew_member(crew_id)


consultant_knowledge_service = ConsultantKnowledgeService()
