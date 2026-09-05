"""Rebuild the contractor search projection from PostgreSQL.

Run after a search-document contract change or a direct database import:

    .venv/bin/python reindex_crew_search.py

PostgreSQL remains authoritative. Approved contractors are written with their
publication status; every non-approved or deleted-from-Postgres contractor is
currently represented in PostgreSQL is removed from the derived Meilisearch
projection. Normal contractor deletion also removes its search document at the
time of deletion.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import get_session_factory
from app.models import CrewMember
from app.services.consultant_knowledge import consultant_knowledge_service


async def rebuild() -> tuple[int, int, int]:
    factory = get_session_factory()
    async with factory() as session:
        crews = list(
            (await session.execute(select(CrewMember).order_by(CrewMember.created_at.asc())))
            .scalars()
            .all()
        )

        approved = sum(crew.publication_status == "approved" for crew in crews)
        indexed = 0
        removed = 0
        for crew in crews:
            if await consultant_knowledge_service.index_crew_member(crew):
                if crew.publication_status == "approved":
                    indexed += 1
                else:
                    removed += 1
        return approved, indexed, removed


if __name__ == "__main__":
    approved_count, indexed_count, removed_count = asyncio.run(rebuild())
    print(
        "Search rebuild complete: "
        f"{indexed_count}/{approved_count} approved contractors indexed; "
        f"{removed_count} non-approved records removed."
    )
    if indexed_count != approved_count:
        raise SystemExit("Search rebuild incomplete: one or more approved records failed")
