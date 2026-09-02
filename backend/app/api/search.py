from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.decorators import get_current_user_rest
from app.services.meilisearch import meilisearch_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/crew")
async def search_crew(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    availability: Optional[str] = Query(None, description="Filter by availability status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user_rest),
):
    """Search crew members using Meilisearch."""
    filters = None
    if availability:
        filters = f'availability_status = "{availability}"'

    results = await meilisearch_client.search_crew_members(
        query=q,
        filters=filters,
        limit=limit,
        offset=offset,
    )
    return results


@router.get("/documents")
async def search_documents(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    classification: Optional[str] = Query(None, description="Filter by document classification"),
    crew_id: Optional[str] = Query(None, description="Filter by crew member ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user_rest),
):
    """Search documents using Meilisearch."""
    filters_parts = []
    if classification:
        filters_parts.append(f'classification = "{classification}"')
    if crew_id:
        filters_parts.append(f'crew_member_id = "{crew_id}"')

    filters = " AND ".join(filters_parts) if filters_parts else None

    results = await meilisearch_client.search_documents(
        query=q,
        filters=filters,
        limit=limit,
        offset=offset,
    )
    return results


@router.post("/index/crew/{crew_id}")
async def index_crew_member(
    crew_id: str, request: Request, current_user=Depends(get_current_user_rest)
):
    """Index a crew member in Meilisearch."""
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models import CrewMember

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(CrewMember).where(CrewMember.id == crew_id)
        result = await session.execute(stmt)
        crew = result.scalar_one_or_none()

        if not crew:
            raise HTTPException(status_code=404, detail="Crew member not found")

        crew_data = {
            "id": crew.id,
            "full_name": crew.full_name,
            "email": crew.email,
            "phone": crew.phone,
            "nationality": crew.nationality,
            "availability_status": crew.availability_status,
            "tags": crew.tags or [],
        }

        task = await meilisearch_client.index_crew_member(crew_data)
        return {"status": "indexed", "task": task}


@router.get("/health")
async def search_health():
    """Check Meilisearch health."""
    healthy = await meilisearch_client.health_check()
    return {"status": "healthy" if healthy else "unhealthy", "service": "meilisearch"}
