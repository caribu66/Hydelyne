from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.decorators import get_current_user_rest, require_admin_rest
from app.domain.fields import AVAILABILITY_STATUS_VALUES, DOCUMENT_CLASSIFICATIONS
from app.models import CrewMember
from app.services.meilisearch import meilisearch_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


def _quote_filter_value(field: str, value: str, allowed: tuple[str, ...]) -> str:
    """Build a Meilisearch filter clause, rejecting values outside the enum.

    Meilisearch filter strings are interpreted, not parameterized — a value
    containing `"` (or filter keywords like `OR`) can break out of the
    intended clause and inject arbitrary filter syntax. Since every caller
    here filters on a closed, small enum, allowlisting is both sufficient and
    simpler than escaping.
    """
    if value not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {field}: must be one of {', '.join(allowed)}",
        )
    return f'{field} = "{value}"'


def _validated_crew_id(crew_id: str) -> str:
    """Validate crew_id is a well-formed UUID before it reaches a filter string.

    CrewMember.id is generated via uuid.uuid4() (see app/models/__init__.py),
    so a syntactically valid UUID cannot contain the quote/keyword characters
    a Meilisearch filter clause would misinterpret.
    """
    try:
        return str(uuid.UUID(crew_id))
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid crew_id: must be a UUID") from None


@router.get("/crew")
async def search_crew(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    availability: Optional[str] = Query(None, description="Filter by availability status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CrewMember = Depends(get_current_user_rest),
) -> dict[str, Any]:
    """Search crew members using Meilisearch."""
    filters = None
    if availability:
        filters = _quote_filter_value(
            "availability_status", availability, AVAILABILITY_STATUS_VALUES
        )

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
    current_user: CrewMember = Depends(get_current_user_rest),
) -> dict[str, Any]:
    """Search documents using Meilisearch."""
    filters_parts = []
    if classification:
        filters_parts.append(
            _quote_filter_value("classification", classification, DOCUMENT_CLASSIFICATIONS)
        )
    if crew_id:
        filters_parts.append(f'crew_member_id = "{_validated_crew_id(crew_id)}"')

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
    crew_id: str, request: Request, current_user: CrewMember = Depends(require_admin_rest)
) -> dict[str, Any]:
    """Index a crew member in Meilisearch.

    State-changing (writes to the Meilisearch index), so it follows the same
    admin-only policy as every other write path — see docs/AUTHORIZATION.md.
    """
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
async def search_health() -> dict[str, str]:
    """Check Meilisearch health."""
    healthy = await meilisearch_client.health_check()
    return {"status": "healthy" if healthy else "unhealthy", "service": "meilisearch"}
