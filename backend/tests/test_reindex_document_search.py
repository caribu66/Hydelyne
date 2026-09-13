from unittest.mock import AsyncMock, patch

import pytest


class _Result:
    def scalars(self):
        return self

    def __iter__(self):
        return iter(["document-1", "document-2"])


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def execute(self, _statement):
        return _Result()


@pytest.mark.asyncio
async def test_document_rebuild_removes_indexed_ids_missing_from_postgres():
    import reindex_document_search

    with (
        patch(
            "reindex_document_search.get_session_factory",
            return_value=lambda: _Session(),
        ),
        patch(
            "reindex_document_search.consultant_knowledge_service.reconcile_document_index",
            new=AsyncMock(return_value=True),
        ) as reconcile,
        patch(
            "reindex_document_search.meilisearch_client.list_document_ids",
            new=AsyncMock(return_value=["document-1", "deleted-document"]),
        ),
        patch(
            "reindex_document_search.meilisearch_client.delete_documents",
            new=AsyncMock(return_value=True),
        ) as delete_documents,
    ):
        result = await reindex_document_search.rebuild()

    assert result == (2, 0, 1)
    assert reconcile.await_count == 2
    delete_documents.assert_awaited_once_with(["deleted-document"])
