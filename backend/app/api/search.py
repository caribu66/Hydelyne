from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, or_, select

from app.auth.decorators import get_current_user_rest, require_admin_rest, require_staff_rest
from app.database import get_session_factory
from app.domain.access_tiers import MEILISEARCH_CREW_DENIED_FIELDS, tier_for_role
from app.domain.crew_accounts import is_contractor_profile
from app.domain.crew_query_rules import MAX_SEARCH_QUERY_LENGTH
from app.domain.fields import (
    AVAILABILITY_STATUS_VALUES,
    DOCUMENT_CLASSIFICATIONS,
    normalize_classification,
)
from app.models import CrewMember, Document
from app.services.audit import audit_service
from app.services.consultant_knowledge import _crew_meilisearch_doc
from app.services.meilisearch import (
    APPROVED_CREW_FILTER,
    DOCUMENT_SEARCHABLE_ATTRIBUTES,
    SEARCHABLE_DOCUMENTS_FILTER,
    SearchProviderUnavailable,
    meilisearch_client,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


def _validated_search_query(query: str) -> str:
    """Reject blank input and bound provider work at the HTTP boundary."""
    normalized = query.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="q must not be blank")
    return normalized


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


def _validated_classification(value: str) -> str:
    """Normalize an accepted classification alias before building a filter."""
    cleaned = value.strip().lower()
    normalized = normalize_classification(cleaned)
    if normalized == "other" and cleaned != "other":
        raise HTTPException(
            status_code=422,
            detail=f"Invalid classification: must be one of {', '.join(DOCUMENT_CLASSIFICATIONS)}",
        )
    return normalized


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
    q: str = Query(
        ..., min_length=1, max_length=MAX_SEARCH_QUERY_LENGTH, description="Search query"
    ),
    availability: Optional[str] = Query(None, description="Filter by availability status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CrewMember = Depends(get_current_user_rest),
) -> dict[str, Any]:
    """Search crew members using Meilisearch. General index is C1-only."""
    q = _validated_search_query(q)
    filters = APPROVED_CREW_FILTER
    if availability:
        availability_filter = _quote_filter_value(
            "availability_status", availability, AVAILABILITY_STATUS_VALUES
        )
        filters = f"{filters} AND {availability_filter}"

    try:
        results = await meilisearch_client.search_crew_members(
            query=q,
            filters=filters,
            limit=limit,
            offset=offset,
        )
    except SearchProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail="Crew search is temporarily unavailable") from exc
    # Meilisearch is a derived projection. Recheck publication state in the
    # source of truth so a stale approved flag cannot expose a withdrawn draft.
    raw_hits_value = results.get("hits", [])
    raw_hits = (
        [hit for hit in raw_hits_value if isinstance(hit, dict)]
        if isinstance(raw_hits_value, list)
        else []
    )
    hit_ids = {str(hit.get("id")) for hit in raw_hits if hit.get("id") is not None}
    source_crews: dict[str, CrewMember] = {}
    if hit_ids:
        async with get_session_factory()() as session:
            source_stmt = select(CrewMember).where(
                CrewMember.id.in_(hit_ids),
                CrewMember.publication_status == "approved",
                CrewMember.password_hash.is_(None),
                or_(CrewMember.role.is_(None), CrewMember.role.not_in(("staff", "admin"))),
            )
            if availability:
                source_stmt = source_stmt.where(CrewMember.availability_status == availability)
            source_rows = await session.execute(source_stmt)
            source_crews = {crew.id: crew for crew in source_rows.scalars().all()}
    # Every hit must resolve to an approved PostgreSQL row. In particular,
    # malformed projection records without an ID must not pass through.
    results["hits"] = []
    for hit in raw_hits:
        crew = source_crews.get(str(hit.get("id")))
        if crew is None:
            continue
        authoritative_hit = _crew_meilisearch_doc(crew)
        # Preserve provider ranking metadata while replacing all indexed
        # profile fields with the PostgreSQL source of truth.
        authoritative_hit.update({key: value for key, value in hit.items() if key.startswith("_")})
        results["hits"].append(authoritative_hit)
    # Keep Meilisearch's estimate: the filtered page is not the complete
    # result set, so replacing the estimate with its length would break
    # pagination whenever stale projection records are removed.
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
    q: str = Query(
        ..., min_length=1, max_length=MAX_SEARCH_QUERY_LENGTH, description="Search query"
    ),
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
    q = _validated_search_query(q)
    # Never expose processing, rejected, or failed extraction records through
    # the document search surface. Reviewers use the CV review queue instead.
    filters_parts = [SEARCHABLE_DOCUMENTS_FILTER]
    visible_crew_ids: set[str] | None = None
    validated_crew_id: str | None = None
    if classification:
        classification = _validated_classification(classification)
        filters_parts.append(
            _quote_filter_value("classification", classification, DOCUMENT_CLASSIFICATIONS)
        )
    if crew_id:
        validated_crew_id = _validated_crew_id(crew_id)
        filters_parts.append(f'crew_member_id = "{validated_crew_id}"')
    if current_user.role != "admin":
        # Publication and draft ownership live in PostgreSQL, not in the
        # document projection. Scope staff searches from the source of truth
        # so another staff member's unpublished draft cannot be discovered.
        async with get_session_factory()() as session:
            visible_rows = await session.execute(
                select(CrewMember.id).where(
                    CrewMember.password_hash.is_(None),
                    or_(CrewMember.role.is_(None), CrewMember.role.not_in(("staff", "admin"))),
                    or_(
                        CrewMember.publication_status == "approved",
                        and_(
                            CrewMember.publication_status == "draft",
                            CrewMember.submitted_by == current_user.id,
                        ),
                    )
                )
            )
            visible_crew_ids = set(visible_rows.scalars().all())
        if not visible_crew_ids:
            return {"hits": [], "estimated_total_hits": 0, "processing_time_ms": 0}
        # Serialize trusted database values as a Meilisearch IN list instead
        # of interpolating request data. JSON escaping also keeps legacy,
        # non-UUID imported IDs from turning this boundary into a 500.
        filters_parts.append(
            "crew_member_id IN " + json.dumps(sorted(visible_crew_ids), separators=(",", ":"))
        )
    filters = " AND ".join(filters_parts) if filters_parts else None

    try:
        results = await meilisearch_client.search_documents(
            query=q,
            filters=filters,
            limit=limit,
            offset=offset,
            # C3 extracted evidence must never be a discovery channel through the
            # general index. T3 admins may receive evidence for an already matched
            # document, but the index itself contains metadata only.
            searchable_attributes=(
                None
                if current_user.role == "admin"
                else list(DOCUMENT_SEARCHABLE_ATTRIBUTES)
            ),
        )
    except SearchProviderUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Document search is temporarily unavailable"
        ) from exc
    # Meilisearch is a derived projection. Recheck every returned document in
    # PostgreSQL so deletion, status changes, or a stale crew scope cannot
    # leak a record through the search API. This applies to admins too: their
    # wider authorization does not make deleted or non-searchable documents
    # valid again.
    raw_hits_value = results.get("hits", [])
    raw_hits = (
        [hit for hit in raw_hits_value if isinstance(hit, dict)]
        if isinstance(raw_hits_value, list)
        else []
    )
    hit_ids = {str(hit.get("id")) for hit in raw_hits if hit.get("id") is not None}
    source_documents: dict[str, Document] = {}
    authoritative_hits: list[dict[str, Any]] = []
    if hit_ids:
        async with get_session_factory()() as session:
            source_stmt = select(Document).where(
                Document.id.in_(hit_ids),
                Document.extraction_status.in_(("approved", "extracted")),
                or_(
                    Document.uploaded_by.is_(None),
                    Document.uploaded_by != "contractor-upload-link",
                    Document.extraction_status == "approved",
                ),
            )
            # Meilisearch is derived state and may retain a searchable
            # document after its contractor is moved back to draft. Search
            # must obey the publication boundary even for administrators;
            # only unowned orphan records remain an admin recovery surface.
            source_stmt = source_stmt.outerjoin(
                CrewMember, Document.crew_member_id == CrewMember.id
            ).where(
                or_(
                    Document.crew_member_id.is_(None),
                    and_(
                        CrewMember.publication_status == "approved",
                        CrewMember.password_hash.is_(None),
                        or_(
                            CrewMember.role.is_(None),
                            CrewMember.role.not_in(("staff", "admin")),
                        ),
                    ),
                )
            )
            if classification:
                source_stmt = source_stmt.where(Document.classification == classification)
            if visible_crew_ids is not None:
                source_stmt = source_stmt.where(Document.crew_member_id.in_(visible_crew_ids))
            if validated_crew_id is not None:
                source_stmt = source_stmt.where(Document.crew_member_id == validated_crew_id)
            source_rows = await session.execute(source_stmt)
            source_documents = {document.id: document for document in source_rows.scalars().all()}

            for hit in raw_hits:
                document = source_documents.get(str(hit.get("id")))
                if document is None:
                    continue
                authoritative_hits.append(
                    {
                        "id": document.id,
                        "crew_member_id": document.crew_member_id,
                        "file_name": document.file_name,
                        "file_type": document.file_type,
                        "file_size": document.file_size,
                        "storage_type": document.storage_type,
                        "classification": document.classification,
                        "extraction_status": document.extraction_status,
                        "extracted_text": document.extracted_text,
                        "extracted_data": document.extracted_data,
                        "extraction_confidence": document.extraction_confidence,
                        "uploaded_by": document.uploaded_by,
                        "uploaded_at": document.uploaded_at,
                        "version_number": document.version_number,
                    }
                )
    # Always replace the derived hits, including when no hit has a usable ID.
    # This prevents malformed or stale payloads from bypassing the source of
    # truth check and returning C3 evidence directly from Meilisearch.
    results["hits"] = authoritative_hits
    # Do not replace estimated_total_hits with the filtered page length: this
    # page is only a slice of the provider result set and may contain stale
    # records that were removed by the source-of-truth check.
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

        if not await consultant_knowledge_service.index_crew_member(crew):
            raise HTTPException(status_code=503, detail="Search index unavailable")
        return {
            "status": (
                "indexed"
                if crew.publication_status == "approved" and is_contractor_profile(crew)
                else "excluded"
            )
        }


@router.get("/health")
async def search_health() -> dict[str, str]:
    """Check Meilisearch health."""
    healthy = await meilisearch_client.health_check()
    return {"status": "healthy" if healthy else "unhealthy", "service": "meilisearch"}
