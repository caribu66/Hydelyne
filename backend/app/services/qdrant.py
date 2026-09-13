from __future__ import annotations

import json
import logging
import math
from typing import TYPE_CHECKING, Any, Optional

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import get_settings

if TYPE_CHECKING:
    from app.models import Document

settings = get_settings()
logger = logging.getLogger(__name__)

QDRANT_COLLECTION = "documents"
VECTOR_SIZE = 384
MAX_EMBEDDING_RESPONSE_BYTES = 256 * 1024


class SemanticSearchProviderUnavailable(RuntimeError):
    """Raised when Qdrant or embedding generation cannot serve a search."""


def document_indexable_text(document: "Document") -> str:
    """Return C2-only text for the general document embedding projection.

    ``extracted_data`` is C3 and must remain PostgreSQL-only unless a
    separately authorized compliance projection is introduced. Keeping this
    helper limited to document metadata also protects both callers: the
    Celery indexing task and similar-document search.
    """
    if document.classification:
        return f"{document.classification} document {document.file_name}"
    return document.file_name


class QdrantService:
    """Service for vector search using Qdrant."""

    def __init__(self) -> None:
        self._client: Optional[QdrantClient] = None
        self._collection_ensured = False

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        if not self._collection_ensured:
            try:
                self._ensure_collection(self._client)
            except Exception as exc:
                logger.warning(
                    "Qdrant not available, collection check skipped (%s)", type(exc).__name__
                )
        return self._client

    def _ensure_collection(self, client: QdrantClient) -> None:
        """Ensure the documents collection exists."""
        try:
            collections = client.get_collections().collections
            collection_names = [c.name for c in collections]
            if QDRANT_COLLECTION not in collection_names:
                client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {QDRANT_COLLECTION}")
            self._collection_ensured = True
        except Exception as exc:
            logger.warning("Failed to ensure Qdrant collection (%s)", type(exc).__name__)
            raise

    async def index_document(
        self,
        document_id: str,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Index a document embedding in Qdrant."""
        import asyncio

        return await asyncio.to_thread(self.index_document_sync, document_id, text, metadata)

    def index_document_sync(
        self,
        document_id: str,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Synchronous index a document embedding in Qdrant."""
        try:
            embedding = self._generate_embedding(text)
            point = PointStruct(
                id=document_id,
                vector=embedding,
                payload=metadata or {},
            )
            self.client.upsert(collection_name=QDRANT_COLLECTION, points=[point])
            logger.info(f"Indexed document {document_id} in Qdrant")
            return True
        except Exception as exc:
            logger.error("Failed to index document %s (%s)", document_id, type(exc).__name__)
            return False

    async def search_similar(
        self,
        query_text: str,
        limit: int = 10,
        score_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search for similar documents."""
        import asyncio

        def _sync() -> list[dict[str, Any]]:
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
        except Exception as exc:
            logger.error("Semantic search failed (%s)", type(exc).__name__)
            raise SemanticSearchProviderUnavailable(
                "Semantic search is temporarily unavailable"
            ) from exc

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document from the index."""
        import asyncio

        return await asyncio.to_thread(self.delete_document_sync, document_id)

    def delete_document_sync(self, document_id: str) -> bool:
        """Delete a document from Qdrant for synchronous worker callers."""
        from qdrant_client.models import PointIdsList

        try:
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
        except Exception as exc:
            logger.error("Failed to delete document %s (%s)", document_id, type(exc).__name__)
            return False
        return True

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for text.

        Uses Ollama embeddings or raises to avoid indexing zero vectors.
        """
        try:
            with httpx.Client(timeout=30.0) as client:
                with client.stream(
                    "POST",
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={
                        "model": settings.OLLAMA_EMBEDDING_MODEL,
                        "prompt": text[:2048],
                    },
                ) as response:
                    if response.status_code != 200:
                        raise RuntimeError("embedding provider returned an error")
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            if int(content_length) > MAX_EMBEDDING_RESPONSE_BYTES:
                                raise RuntimeError("embedding response is too large")
                        except ValueError:
                            pass
                    chunks: list[bytes] = []
                    total_bytes = 0
                    for chunk in response.iter_bytes():
                        total_bytes += len(chunk)
                        if total_bytes > MAX_EMBEDDING_RESPONSE_BYTES:
                            raise RuntimeError("embedding response is too large")
                        chunks.append(chunk)
                    payload = json.loads(b"".join(chunks))
            if isinstance(payload, dict):
                emb = payload.get("embedding")
                if isinstance(emb, list) and len(emb) == VECTOR_SIZE:
                    vector = [float(x) for x in emb]
                    if all(math.isfinite(value) for value in vector):
                        return vector
            logger.warning("Ollama returned empty or malformed embedding")
        except Exception as exc:
            logger.warning("Ollama embedding failed (%s)", type(exc).__name__)

        raise RuntimeError("Embedding generation failed — skipping indexing to avoid zero vector")


qdrant_service = QdrantService()
