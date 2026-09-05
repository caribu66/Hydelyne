"""Rebuild the contractor search projection from PostgreSQL.

Run after a search-document contract change or a direct database import:

    .venv/bin/python reindex_crew_search.py

PostgreSQL remains authoritative. Approved contractors are written with their
publication status; every non-approved or deleted-from-Postgres contractor is
currently represented in PostgreSQL is removed from the derived Meilisearch
projection. Normal contractor deletion also removes its search document at the
time of deletion.
"""

import argparse
import asyncio

from app.database import get_session_factory
from app.services.consultant_knowledge import consultant_knowledge_service


async def rebuild(batch_size: int = 200) -> tuple[int, int, int]:
    factory = get_session_factory()
    return await consultant_knowledge_service.reindex_all_crew(factory, batch_size=batch_size)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild contractor search projection in Meilisearch.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Number of records to fetch and batch per iteration (default: 200)",
    )
    args = parser.parse_args()

    approved_count, indexed_count, removed_count = asyncio.run(rebuild(batch_size=args.batch_size))
    print(
        "Search rebuild complete: "
        f"{indexed_count}/{approved_count} approved contractors indexed; "
        f"{removed_count} non-approved records removed."
    )
    if indexed_count != approved_count:
        raise SystemExit("Search rebuild incomplete: one or more approved records failed")
