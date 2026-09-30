from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from app.config import get_settings

if TYPE_CHECKING:
    # `meilisearch` actually ships real inline types (py.typed) — no need
    # for a hand-rolled Protocol. Imported only for type-checking so the
    # real client construction below stays lazy (avoids importing/paying
    # for the client library on every process that imports this module).
    from meilisearch import Client

settings = get_settings()
logger = logging.getLogger(__name__)

CREW_MEMBERS_INDEX = "crew_members"
DOCUMENTS_INDEX = "documents"
APPROVED_CREW_FILTER = 'publication_status = "approved"'
SEARCHABLE_DOCUMENTS_FILTER = 'extraction_status IN ["approved", "extracted"]'
DOCUMENT_SEARCHABLE_ATTRIBUTES = ("file_name", "file_type", "classification")
# Bound every synchronous provider call (all run in worker threads via
# to_thread): without this a hung Meilisearch parks the thread indefinitely
# and repeated stalls exhaust the pool. Kept above the 5s task-wait window
# so configuration waits fail on their own terms, not on the socket.
MEILISEARCH_REQUEST_TIMEOUT_SECONDS = 10


class SearchProviderUnavailable(RuntimeError):
    """Raised when Meilisearch cannot serve a search request."""


class MeilisearchClient:
    """Client for Meilisearch full-text search."""

    def __init__(self) -> None:
        self.base_url = f"http://{settings.MEILI_HOST}:{settings.MEILI_PORT}"
        self.master_key = getattr(settings, "MEILI_MASTER_KEY", "")
        self._client: Optional["Client"] = None

    @property
    def client(self) -> "Client":
        if self._client is None:
            import meilisearch

            self._client = meilisearch.Client(
                self.base_url, self.master_key, timeout=MEILISEARCH_REQUEST_TIMEOUT_SECONDS
            )
        return self._client

    def _wait_for_task(self, task_uid: int) -> bool:
        """Confirm that an asynchronous Meilisearch write actually completed."""
        task = self.client.wait_for_task(task_uid, timeout_in_ms=5000, interval_in_ms=50)
        return getattr(task, "status", None) == "succeeded"

    async def health_check(self) -> bool:
        """Check if Meilisearch is available."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                async with client.stream("GET", f"{self.base_url}/health") as response:
                    return response.status_code == 200
        except Exception:
            return False

    async def setup_indexes(self) -> None:
        """Create and configure search indexes.

        Failures propagate: boot keeps serving (see the lifespan handler in
        app/main.py, which logs and continues), but the failure stays
        observable instead of booting with silently unconfigured indexes.
        """
        import asyncio

        def _sync_setup() -> None:
            # Crew members index — client.index() is a lazy handle and never
            # raises, so create unconditionally and tolerate already-exists.
            try:
                self.client.create_index(CREW_MEMBERS_INDEX, {"primaryKey": "id"})
            except Exception as exc:
                logger.debug(
                    "Meilisearch crew index creation was skipped (%s); it may already exist",
                    type(exc).__name__,
                )

            crew_index = self.client.index(CREW_MEMBERS_INDEX)
            # C1-only searchable attributes per ADR 0005 — email/phone and
            # passport/visa/medical/insurance derived fields must never be
            # searchable in the general index.
            crew_index_tasks = [
                crew_index.update_searchable_attributes(
                    [
                        "full_name",
                        "nationality",
                        "country_of_residence",
                        "gender",
                        "languages",
                        "flying_point",
                        "education",
                        "tags",
                        "training_qualifications",
                        "geographical_experience",
                        "systems_experience",
                        "professional_summary",
                    ]
                ),
                crew_index.update_filterable_attributes(
                    [
                        "availability_status",
                        "nationality",
                        "country_of_residence",
                        "gender",
                        "languages",
                        "tags",
                        "publication_status",
                    ]
                ),
                crew_index.update_sortable_attributes(
                    [
                        "created_at",
                        "availability_date",
                        "full_name",
                    ]
                ),
            ]

            # Documents index — same lazy-handle reasoning as above.
            try:
                self.client.create_index(DOCUMENTS_INDEX, {"primaryKey": "id"})
            except Exception as exc:
                logger.debug(
                    "Meilisearch document index creation was skipped (%s); it may already exist",
                    type(exc).__name__,
                )

            doc_index = self.client.index(DOCUMENTS_INDEX)
            document_index_tasks = [
                doc_index.update_searchable_attributes([*DOCUMENT_SEARCHABLE_ATTRIBUTES]),
                doc_index.update_filterable_attributes(
                    [
                        "file_type",
                        "classification",
                        "extraction_status",
                        "crew_member_id",
                    ]
                ),
            ]
            for task in [*crew_index_tasks, *document_index_tasks]:
                if not self._wait_for_task(task.task_uid):
                    raise RuntimeError("Meilisearch index configuration task did not succeed")

        await asyncio.to_thread(_sync_setup)
        logger.info("Meilisearch indexes configured successfully")

    async def index_crew_member(self, crew_member: dict[str, Any]) -> Optional[dict[str, int]]:
        """Index a crew member for search."""
        import asyncio

        def _sync() -> dict[str, int]:
            index = self.client.index(CREW_MEMBERS_INDEX)
            task = index.add_documents([crew_member])
            if not self._wait_for_task(task.task_uid):
                raise RuntimeError("Meilisearch crew index task did not succeed")
            return {"task_uid": task.task_uid}

        try:
            return await asyncio.to_thread(_sync)
        except Exception as exc:
            logger.error("Failed to index crew member (%s)", type(exc).__name__)
            return None

    async def index_crew_members(
        self, crew_members: list[dict[str, Any]]
    ) -> Optional[dict[str, int]]:
        """Index multiple crew members for search."""
        import asyncio

        def _sync() -> dict[str, int]:
            index = self.client.index(CREW_MEMBERS_INDEX)
            task = index.add_documents(crew_members)
            if not self._wait_for_task(task.task_uid):
                raise RuntimeError("Meilisearch crew batch task did not succeed")
            return {"task_uid": task.task_uid}

        try:
            return await asyncio.to_thread(_sync)
        except Exception as exc:
            logger.error("Failed to index crew members (%s)", type(exc).__name__)
            return None

    async def search_crew_members(
        self,
        query: str,
        filters: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search crew members."""
        import asyncio

        def _sync() -> dict[str, Any]:
            index = self.client.index(CREW_MEMBERS_INDEX)
            search_params: dict[str, Any] = {
                "limit": limit,
                "offset": offset,
            }
            search_params["filter"] = (
                f"{APPROVED_CREW_FILTER} AND {filters}" if filters else APPROVED_CREW_FILTER
            )
            results: dict[str, Any] = index.search(query, search_params)
            return results

        try:
            results = await asyncio.to_thread(_sync)
            return {
                "hits": results.get("hits", []),
                "estimated_total_hits": results.get("estimatedTotalHits", 0),
                "processing_time_ms": results.get("processingTimeMs", 0),
            }
        except Exception as exc:
            logger.error("Failed to search crew members (%s)", type(exc).__name__)
            raise SearchProviderUnavailable("Crew search is temporarily unavailable") from exc

    async def delete_crew_member(self, crew_id: str) -> bool:
        """Delete a crew member from the index."""
        import asyncio

        def _sync() -> bool:
            index = self.client.index(CREW_MEMBERS_INDEX)
            task = index.delete_document(crew_id)
            return self._wait_for_task(task.task_uid)

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error("Failed to delete crew member from index: %s", type(e).__name__)
            return False

    async def delete_crew_members(self, crew_ids: list[str]) -> bool:
        """Delete multiple crew members from the index in batch."""
        if not crew_ids:
            return True
        import asyncio

        def _sync() -> bool:
            index = self.client.index(CREW_MEMBERS_INDEX)
            task = index.delete_documents(crew_ids)
            return self._wait_for_task(task.task_uid)

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error("Failed to delete crew members from index: %s", type(e).__name__)
            return False

    async def list_crew_member_ids(self, *, batch_size: int = 1000) -> Optional[list[str]]:
        """Return all IDs currently in the crew projection.

        ``None`` means the index could not be read. Callers must distinguish
        that from an empty index so a transient Meilisearch failure cannot be
        interpreted as proof that every indexed record is stale.
        """
        import asyncio

        batch_size = max(1, min(batch_size, 10_000))

        def _sync() -> list[str]:
            index = self.client.index(CREW_MEMBERS_INDEX)
            offset = 0
            ids: list[str] = []
            while True:
                page = index.get_documents(
                    {
                        "fields": ["id"],
                        "limit": batch_size,
                        "offset": offset,
                    }
                )
                page_ids = [
                    str(document_id)
                    for document in page.results
                    if (document_id := getattr(document, "id", None)) is not None
                ]
                ids.extend(page_ids)
                if not page.results or offset + len(page.results) >= page.total:
                    return ids
                offset += len(page.results)

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error("Failed to list crew member IDs from index: %s", type(e).__name__)
            return None

    async def index_document(self, document: dict[str, Any]) -> Optional[dict[str, int]]:
        """Index a document for search."""
        import asyncio

        def _sync() -> dict[str, int]:
            index = self.client.index(DOCUMENTS_INDEX)
            task = index.add_documents([document])
            if not self._wait_for_task(task.task_uid):
                raise RuntimeError("Meilisearch document index task did not succeed")
            return {"task_uid": task.task_uid}

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error("Failed to index document: %s", type(e).__name__)
            return None

    async def delete_document(self, document_id: str) -> bool:
        """Remove a document projection from the search index."""
        import asyncio

        def _sync() -> bool:
            index = self.client.index(DOCUMENTS_INDEX)
            task = index.delete_document(document_id)
            return self._wait_for_task(task.task_uid)

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error("Failed to remove document from search index: %s", type(e).__name__)
            return False

    async def delete_documents(self, document_ids: list[str]) -> bool:
        """Remove multiple document projections from the search index."""
        if not document_ids:
            return True
        import asyncio

        def _sync() -> bool:
            index = self.client.index(DOCUMENTS_INDEX)
            task = index.delete_documents(document_ids)
            return self._wait_for_task(task.task_uid)

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error(
                "Failed to remove document projections from search index: %s",
                type(e).__name__,
            )
            return False

    async def list_document_ids(self, *, batch_size: int = 1000) -> Optional[list[str]]:
        """Return all IDs currently in the document projection.

        ``None`` means the index could not be read. Callers must distinguish
        that from an empty index so a transient Meilisearch failure cannot be
        interpreted as proof that every indexed record is stale.
        """
        import asyncio

        batch_size = max(1, min(batch_size, 10_000))

        def _sync() -> list[str]:
            index = self.client.index(DOCUMENTS_INDEX)
            offset = 0
            ids: list[str] = []
            while True:
                page = index.get_documents(
                    {"fields": ["id"], "limit": batch_size, "offset": offset}
                )
                page_ids = [
                    str(document_id)
                    for document in page.results
                    if (document_id := getattr(document, "id", None)) is not None
                ]
                ids.extend(page_ids)
                if not page.results or offset + len(page.results) >= page.total:
                    return ids
                offset += len(page.results)

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error("Failed to list document IDs from search index: %s", type(e).__name__)
            return None

    async def search_documents(
        self,
        query: str,
        filters: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        searchable_attributes: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Search documents, optionally restricting searchable attributes."""
        import asyncio

        def _sync() -> dict[str, Any]:
            index = self.client.index(DOCUMENTS_INDEX)
            search_params: dict[str, Any] = {
                "limit": limit,
                "offset": offset,
            }
            if filters:
                search_params["filter"] = filters
            if searchable_attributes is not None:
                search_params["attributesToSearchOn"] = searchable_attributes
            results: dict[str, Any] = index.search(query, search_params)
            return results

        try:
            results = await asyncio.to_thread(_sync)
            return {
                "hits": results.get("hits", []),
                "estimated_total_hits": results.get("estimatedTotalHits", 0),
                "processing_time_ms": results.get("processingTimeMs", 0),
            }
        except Exception as exc:
            logger.error("Failed to search documents (%s)", type(exc).__name__)
            raise SearchProviderUnavailable("Document search is temporarily unavailable") from exc


meilisearch_client = MeilisearchClient()
