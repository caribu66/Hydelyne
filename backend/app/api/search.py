from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.decorators import get_current_user_rest, require_admin_rest, require_staff_rest
from app.domain.access_tiers import MEILISEARCH_CREW_DENIED_FIELDS, tier_for_role
from app.domain.fields import AVAILABILITY_STATUS_VALUES, DOCUMENT_CLASSIFICATIONS
from app.models import CrewMember
from app.services.audit import audit_service
from app.services.meilisearch import (
    APPROVED_CREW_FILTER,
    SEARCHABLE_DOCUMENTS_FILTER,
    meilisearch_client,
)

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
    """Search crew members using Meilisearch. General index is C1-only."""
    filters = APPROVED_CREW_FILTER
    if availability:
        availability_filter = _quote_filter_value(
            "availability_status", availability, AVAILABILITY_STATUS_VALUES
        )
        filters = f"{filters} AND {availability_filter}"

    results = await meilisearch_client.search_crew_members(
        query=q,
        filters=filters,
        limit=limit,
        offset=offset,
    )
    # Defense-in-depth: strip any denied fields that might remain from a
    # pre-migration index (old docs still contain email/phone).
    for hit in results.get("hits", []) or []:
        for denied in MEILISEARCH_CREW_DENIED_FIELDS:
            hit.pop(denied, None)
        # Also strip denormalized keys that map to denied storage
        hit.pop("extracted_data", None)
        hit.pop("extracted_text", None)
    hits = results.get("hits")
    await audit_service.log_profile_access(
        actor_id=current_user.id,
        action="keyword_search",
        result_count=len(hits) if isinstance(hits, list) else 0,
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
    current_user: CrewMember = Depends(require_staff_rest),
) -> dict[str, Any]:
    """Search documents using Meilisearch. Requires T2 (staff/admin) — C2 metadata.

    C3 evidence (extracted_data) is stripped for T2 and only returned for T3.
    Never expose processing, rejected, or failed extraction records.
    """
    # Never expose processing, rejected, or failed extraction records through
    # the document search surface. Reviewers use the CV review queue instead.
    filters_parts = [SEARCHABLE_DOCUMENTS_FILTER]
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
    tier = tier_for_role(current_user.role)
    if tier != "T3":
        for hit in results.get("hits", []) or []:
            hit.pop("extracted_data", None)
            hit.pop("extracted_text", None)
            hit.pop("extraction_confidence", None)
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

        from app.services.consultant_knowledge import consultant_knowledge_service

        await consultant_knowledge_service.index_crew_member(crew)
        return {"status": "indexed" if crew.publication_status == "approved" else "excluded"}


@router.get("/health")
async def search_health() -> dict[str, str]:
    """Check Meilisearch health."""
    healthy = await meilisearch_client.health_check()
    return {"status": "healthy" if healthy else "unhealthy", "service": "meilisearch"}
