"""Rebuild the document search projection from PostgreSQL.

Run after deploying the document-search projection or importing document rows:

    .venv/bin/python reindex_document_search.py

PostgreSQL remains authoritative. Non-searchable, deleted, unpublished, and
review-gated documents are removed from Meilisearch during the same pass.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Document
from app.services.consultant_knowledge import consultant_knowledge_service
from app.services.meilisearch import meilisearch_client


async def rebuild() -> tuple[int, int, int]:
    factory = get_session_factory()
    async with factory() as session:
        document_ids = list(
            (await session.execute(select(Document.id).order_by(Document.id))).scalars()
        )

    indexed = 0
    failed = 0
    for document_id in document_ids:
        if await consultant_knowledge_service.reconcile_document_index(document_id):
            indexed += 1
        else:
            failed += 1

    indexed_ids = await meilisearch_client.list_document_ids()
    removed = 0
    if indexed_ids is None:
        failed += 1
    else:
        authoritative_ids = set(document_ids)
        stale_ids = [document_id for document_id in indexed_ids if document_id not in authoritative_ids]
        for start in range(0, len(stale_ids), 1000):
            batch = stale_ids[start : start + 1000]
            if await meilisearch_client.delete_documents(batch):
                removed += len(batch)
            else:
                failed += 1
    return indexed, failed, removed


if __name__ == "__main__":
    argparse.ArgumentParser(description="Rebuild the document Meilisearch projection.").parse_args()
    indexed_count, failed_count, removed_count = asyncio.run(rebuild())
    print(
        f"Document search rebuild complete: {indexed_count} succeeded; "
        f"{removed_count} stale records removed; {failed_count} failed"
    )
    if failed_count:
        raise SystemExit("Document search rebuild incomplete")
