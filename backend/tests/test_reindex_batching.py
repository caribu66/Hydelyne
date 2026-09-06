"""Tests for keyset-paginated search reindexing and Meilisearch batching."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models import CrewMember
from app.services.consultant_knowledge import consultant_knowledge_service
from tests.conftest import test_session_factory


@pytest.mark.asyncio
async def test_reindex_all_crew_keyset_batching():
    """Verify reindex_all_crew iterates in batches using keyset pagination and batches Meilisearch operations."""
    async with test_session_factory() as session:
        # Create 5 test crew members (3 approved, 2 pending/draft)
        for i in range(5):
            member = CrewMember(
                id=f"reindex-test-{i:03d}",
                full_name=f"Reindex Specialist {i}",
                email=f"spec{i}@example.com",
                role="geophysicist",
                publication_status="approved" if i % 2 == 0 else "draft",
            )
            session.add(member)
        await session.commit()

    # Mock meilisearch client batch methods
    with (
        patch(
            "app.services.consultant_knowledge.meilisearch_client.index_crew_members",
            new_callable=AsyncMock,
        ) as mock_index_batch,
        patch(
            "app.services.consultant_knowledge.meilisearch_client.delete_crew_members",
            new_callable=AsyncMock,
        ) as mock_delete_batch,
    ):
        mock_index_batch.return_value = {"task_uid": 123}
        mock_delete_batch.return_value = True

        # Run with batch_size=2 to force multi-chunk keyset pagination
        (
            total_approved,
            total_indexed,
            total_removed,
        ) = await consultant_knowledge_service.reindex_all_crew(test_session_factory, batch_size=2)

        assert total_approved >= 3
        assert total_indexed >= 3
        assert total_removed >= 2

        # Verify bulk methods were invoked rather than single-item methods
        assert mock_index_batch.called
        assert mock_delete_batch.called

        # Verify all batch payloads passed to index_crew_members have publication_status == 'approved'
        for call_args in mock_index_batch.call_args_list:
            batch = call_args[0][0]
            assert isinstance(batch, list)
            for doc in batch:
                assert doc["publication_status"] == "approved"
