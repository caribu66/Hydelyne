from __future__ import annotations

import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

QDRANT_COLLECTION = "documents"
VECTOR_SIZE = 384


def document_indexable_text(document) -> str:
    """The text embedded for a Document: prefer its structured extraction,
    fall back to classification/file name. Shared by the embedding-indexing
    Celery task and ConsultantKnowledgeService.similar_documents so both
    embed the same document the same way."""
    import json as _json

    if document.extracted_data:
        return _json.dumps(document.extracted_data, default=str)
    if document.classification:
        return f"{document.classification} document {document.file_name}"
    return document.file_name


class QdrantService:
    """Service for vector search using Qdrant."""

    def __init__(self):
        self._client: Optional[QdrantClient] = None
        self._collection_ensured = False

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        if not self._collection_ensured:
            try:
                self._ensure_collection()
            except Exception as e:
                logger.warning(f"Qdrant not available, collection check skipped: {e}")
        return self._client

    def _ensure_collection(self) -> None:
        """Ensure the documents collection exists."""
        try:
            collections = self._client.get_collections().collections  # type: ignore[union-attr]
            collection_names = [c.name for c in collections]
            if QDRANT_COLLECTION not in collection_names:
                self._client.create_collection(  # type: ignore[union-attr]
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {QDRANT_COLLECTION}")
            self._collection_ensured = True
        except Exception as e:
            logger.warning(f"Failed to ensure Qdrant collection: {e}")
            raise

    async def index_document(
        self,
        document_id: str,
        text: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Index a document embedding in Qdrant."""
        import asyncio

        def _sync():
            embedding = self._generate_embedding(text)
            point = PointStruct(
                id=document_id,
                vector=embedding,
                payload=metadata or {},
            )
            self.client.upsert(collection_name=QDRANT_COLLECTION, points=[point])
            return True

        try:
            await asyncio.to_thread(_sync)
            logger.info(f"Indexed document {document_id} in Qdrant")
            return True
        except Exception as e:
            logger.error(f"Failed to index document {document_id}: {e}")
            return False

    async def search_similar(
        self,
        query_text: str,
        limit: int = 10,
        score_threshold: float = 0.7,
    ) -> list[dict]:
        """Search for similar documents."""
        import asyncio

        def _sync():
            query_embedding = self._generate_embedding(query_text)
            try:
                results = self.client.query_points(
                    collection_name=QDRANT_COLLECTION,
                    query=query_embedding,
                    limit=limit,
                    score_threshold=score_threshold,
                ).points
            except AttributeError:
                results = self.client.search(
                    collection_name=QDRANT_COLLECTION,
                    query_vector=query_embedding,
                    limit=limit,
                    score_threshold=score_threshold,
                )
            return [
                {
                    "id": str(r.id),
                    "score": r.score,
                    "metadata": r.payload,
                }
                for r in results
            ]

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document from the index."""
        import asyncio

        def _sync():
            from qdrant_client.models import PointIdsList

            try:
                self.client.delete(
                    collection_name=QDRANT_COLLECTION,
                    points_selector=PointIdsList(points=[document_id]),
                )
            except TypeError:
                self.client.delete(
                    collection_name=QDRANT_COLLECTION,
                    points_selector=[document_id],
                )
            return True

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for text.

        Uses Ollama embeddings or raises to avoid indexing zero vectors.
        """
        try:
            import httpx

            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                json={"model": settings.OLLAMA_EMBEDDING_MODEL, "prompt": text[:2048]},
                timeout=30.0,
            )
            if response.status_code == 200:
                emb = response.json().get("embedding")
                if emb:
                    return emb
                logger.warning("Ollama returned empty embedding")
        except Exception as e:
            logger.warning(f"Ollama embedding failed: {e}")

        raise RuntimeError("Embedding generation failed — skipping indexing to avoid zero vector")


qdrant_service = QdrantService()
