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

            self._client = meilisearch.Client(self.base_url, self.master_key)
        return self._client

    async def health_check(self) -> bool:
        """Check if Meilisearch is available."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False

    async def setup_indexes(self) -> None:
        """Create and configure search indexes."""
        import asyncio

        def _sync_setup() -> None:
            # Crew members index
            try:
                self.client.index(CREW_MEMBERS_INDEX)
            except Exception:
                self.client.create_index(CREW_MEMBERS_INDEX, {"primaryKey": "id"})

            crew_index = self.client.index(CREW_MEMBERS_INDEX)
            crew_index.update_searchable_attributes(
                [
                    "full_name",
                    "email",
                    "phone",
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
                ]
            )
            crew_index.update_filterable_attributes(
                [
                    "availability_status",
                    "nationality",
                    "country_of_residence",
                    "gender",
                    "languages",
                    "tags",
                ]
            )
            crew_index.update_sortable_attributes(
                [
                    "created_at",
                    "availability_date",
                    "full_name",
                ]
            )

            # Documents index
            try:
                self.client.index(DOCUMENTS_INDEX)
            except Exception:
                self.client.create_index(DOCUMENTS_INDEX, {"primaryKey": "id"})

            doc_index = self.client.index(DOCUMENTS_INDEX)
            doc_index.update_searchable_attributes(
                [
                    "file_name",
                    "classification",
                    "extracted_data",
                ]
            )
            doc_index.update_filterable_attributes(
                [
                    "file_type",
                    "classification",
                    "extraction_status",
                    "crew_member_id",
                ]
            )

        try:
            await asyncio.to_thread(_sync_setup)
            logger.info("Meilisearch indexes configured successfully")
        except Exception as e:
            logger.error(f"Failed to setup Meilisearch indexes: {e}")

    async def index_crew_member(self, crew_member: dict[str, Any]) -> Optional[dict[str, int]]:
        """Index a crew member for search."""
        import asyncio

        def _sync() -> dict[str, int]:
            index = self.client.index(CREW_MEMBERS_INDEX)
            task = index.add_documents([crew_member])
            return {"task_uid": task.task_uid}

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error(f"Failed to index crew member: {e}")
            return None

    async def index_crew_members(
        self, crew_members: list[dict[str, Any]]
    ) -> Optional[dict[str, int]]:
        """Index multiple crew members for search."""
        import asyncio

        def _sync() -> dict[str, int]:
            index = self.client.index(CREW_MEMBERS_INDEX)
            task = index.add_documents(crew_members)
            return {"task_uid": task.task_uid}

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error(f"Failed to index crew members: {e}")
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
            if filters:
                search_params["filter"] = filters
            return index.search(query, search_params)

        try:
            results = await asyncio.to_thread(_sync)
            return {
                "hits": results.get("hits", []),
                "estimated_total_hits": results.get("estimatedTotalHits", 0),
                "processing_time_ms": results.get("processingTimeMs", 0),
            }
        except Exception as e:
            logger.error(f"Failed to search crew members: {e}")
            return {"hits": [], "estimated_total_hits": 0, "processing_time_ms": 0}

    async def delete_crew_member(self, crew_id: str) -> bool:
        """Delete a crew member from the index."""
        import asyncio

        def _sync() -> bool:
            index = self.client.index(CREW_MEMBERS_INDEX)
            index.delete_document(crew_id)
            return True

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error(f"Failed to delete crew member from index: {e}")
            return False

    async def index_document(self, document: dict[str, Any]) -> Optional[dict[str, int]]:
        """Index a document for search."""
        import asyncio

        def _sync() -> dict[str, int]:
            index = self.client.index(DOCUMENTS_INDEX)
            task = index.add_documents([document])
            return {"task_uid": task.task_uid}

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            return None

    async def search_documents(
        self,
        query: str,
        filters: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search documents."""
        import asyncio

        def _sync() -> dict[str, Any]:
            index = self.client.index(DOCUMENTS_INDEX)
            search_params: dict[str, Any] = {
                "limit": limit,
                "offset": offset,
            }
            if filters:
                search_params["filter"] = filters
            return index.search(query, search_params)

        try:
            results = await asyncio.to_thread(_sync)
            return {
                "hits": results.get("hits", []),
                "estimated_total_hits": results.get("estimatedTotalHits", 0),
                "processing_time_ms": results.get("processingTimeMs", 0),
            }
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return {"hits": [], "estimated_total_hits": 0, "processing_time_ms": 0}


meilisearch_client = MeilisearchClient()
