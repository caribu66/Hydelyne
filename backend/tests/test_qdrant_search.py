"""Failure semantics for the optional semantic-search provider."""

from unittest.mock import patch

import pytest

from app.services.qdrant import (
    SemanticSearchProviderUnavailable,
    qdrant_service,
)


class _EmbeddingResponse:
    headers = {}
    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def iter_bytes(self):
        yield b'{"embedding":"' + (b"x" * 262_145) + b'"}'


class _EmbeddingClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def stream(self, method, url, **kwargs):
        return _EmbeddingResponse()


@pytest.mark.asyncio
async def test_semantic_provider_failure_is_not_reported_as_empty_results():
    with patch.object(
        qdrant_service,
        "_generate_embedding",
        side_effect=RuntimeError("embedding service unavailable"),
    ):
        with pytest.raises(SemanticSearchProviderUnavailable):
            await qdrant_service.search_similar("certificate")


def test_embedding_response_is_bounded_before_json_parsing(monkeypatch):
    import app.services.qdrant as qdrant

    monkeypatch.setattr(qdrant.httpx, "Client", lambda **kwargs: _EmbeddingClient())
    with pytest.raises(RuntimeError, match="Embedding generation failed"):
        qdrant.QdrantService()._generate_embedding("query")


def test_embedding_vector_must_match_qdrant_dimension(monkeypatch):
    import app.services.qdrant as qdrant

    class ValidJsonResponse(_EmbeddingResponse):
        def iter_bytes(self):
            yield b'{"embedding": [1.0]}'

    class ValidJsonClient(_EmbeddingClient):
        def stream(self, method, url, **kwargs):
            return ValidJsonResponse()

    monkeypatch.setattr(qdrant.httpx, "Client", lambda **kwargs: ValidJsonClient())
    with pytest.raises(RuntimeError, match="Embedding generation failed"):
        qdrant.QdrantService()._generate_embedding("query")
