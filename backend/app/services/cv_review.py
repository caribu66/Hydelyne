"""Application service for staged, administrator-reviewed CV ingestion."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_session_factory
from app.domain.crew_accounts import is_contractor_profile
from app.domain.input_limits import MAX_REVIEW_NOTE_LENGTH, validate_pagination
from app.models import CrewMember, CVReview, Document
from app.services.cache import cache_service
from app.services.consultant_knowledge import consultant_knowledge_service
from app.services.cv_processing import cv_processing_service

logger = logging.getLogger(__name__)


async def _repair_crew_projection(crew: CrewMember) -> None:
    """Repair the profile projection without masking a committed review."""
    from app.tasks.document_tasks import queue_crew_projection_reconcile

    try:
        if crew.publication_status == "approved":
            confirmed = await consultant_knowledge_service.index_crew_member(crew)
        else:
            confirmed = await consultant_knowledge_service.remove_from_index(crew.id)
        if not confirmed:
            queue_crew_projection_reconcile(crew.id)
    except Exception as exc:
        logger.warning("Could not repair CV profile projection (%s)", type(exc).__name__)
        queue_crew_projection_reconcile(crew.id)


async def _repair_document_projection(document_id: str) -> None:
    """Repair keyword search projection without masking a committed review."""
    from app.tasks.document_tasks import queue_document_search_reconcile

    try:
        if not await consultant_knowledge_service.reconcile_document_index(document_id):
            queue_document_search_reconcile(document_id)
    except Exception as exc:
        logger.warning("Could not repair CV document projection (%s)", type(exc).__name__)
        queue_document_search_reconcile(document_id)


async def _repair_document_vector(document_id: str) -> None:
    """Repair optional semantic cleanup without masking a committed review."""
    from app.config import get_settings

    if not get_settings().ENABLE_SEMANTIC_SEARCH:
        return
    from app.services.qdrant import qdrant_service
    from app.tasks.document_tasks import queue_document_projection_cleanup

    try:
        if not await qdrant_service.delete_document(document_id):
            queue_document_projection_cleanup(document_id)
    except Exception as exc:
        logger.warning("Could not repair CV document vector (%s)", type(exc).__name__)
        queue_document_projection_cleanup(document_id)


class CVReviewService:
    async def list_visible(
        self,
        *,
        actor_id: str,
        actor_role: str,
        limit: int,
        offset: int,
    ) -> list[CVReview]:
        limit, offset = validate_pagination(limit, offset)
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CVReview).order_by(CVReview.created_at.desc(), CVReview.id.desc())
            if actor_role != "admin":
                stmt = stmt.where(CVReview.submitted_by == actor_id)
            stmt = stmt.limit(limit).offset(offset)
            return list((await session.execute(stmt)).scalars().all())

    async def approve(
        self,
        review_id: str,
        *,
        approved_data: dict[str, Any],
        reviewer_id: str,
        note: str | None = None,
    ) -> CVReview:
        if not isinstance(approved_data, dict):
            raise ValueError("Approved CV data must be a JSON object")
        if note is not None and not isinstance(note, str):
            raise ValueError("Review note must be a string")
        if note is not None and len(note) > MAX_REVIEW_NOTE_LENGTH:
            raise ValueError(
                f"Review note is too large (max {MAX_REVIEW_NOTE_LENGTH} characters)"
            )
        factory = get_session_factory()
        async with factory() as session:
            review = (
                await session.execute(select(CVReview).where(CVReview.id == review_id))
            ).scalar_one_or_none()
            if review is None:
                raise ValueError("CV review not found")
            if review.status == "approved":
                # An earlier successful database commit may have been
                # followed by a derived-index or broker outage. Reconcile
                # those projections on an idempotent approval retry.
                from app.services.crew import crew_service

                crew = await crew_service.get_crew_member(review.crew_member_id)
                if crew is not None:
                    await _repair_crew_projection(crew)
                approved_document_ids = list(
                    (
                        await session.execute(
                            select(Document.id).where(
                                Document.crew_member_id == review.crew_member_id,
                                Document.extraction_status.in_({"approved", "extracted"}),
                            )
                        )
                    ).scalars()
                )
                from app.tasks.document_tasks import _maybe_queue_embeddings

                for approved_document_id in approved_document_ids:
                    _maybe_queue_embeddings(approved_document_id, "approved")
                    await _repair_document_projection(approved_document_id)
                return review
            crew_id = review.crew_member_id
            document_id = review.document_id
            document = (
                await session.execute(
                    select(Document).where(Document.id == document_id).with_for_update()
                )
            ).scalar_one_or_none()
            if document is None:
                raise ValueError("CV document not found")
            if document.crew_member_id != crew_id:
                raise ValueError("CV document does not belong to this contractor")
            review = (
                await session.execute(
                    select(CVReview).where(CVReview.id == review_id).with_for_update()
                )
            ).scalar_one()
            if review.status != "awaiting_review":
                raise ValueError("CV review is not awaiting approval")
            if document.extraction_status != "awaiting_review":
                raise ValueError("CV document is no longer awaiting approval")
            crew = (
                await session.execute(
                    select(CrewMember)
                    .options(
                        selectinload(CrewMember.certifications),
                        selectinload(CrewMember.work_history),
                    )
                    .where(CrewMember.id == crew_id)
                    .with_for_update()
                )
            ).scalar_one()
            if not is_contractor_profile(crew):
                raise ValueError("Crew member not found")
            await cv_processing_service.apply_reviewed_extraction(
                session=session,
                crew_member=crew,
                extracted_data=approved_data,
                document_id=document_id,
                replace_existing=True,
            )
            review.status = "approved"
            review.approved_data = approved_data
            review.reviewed_by = reviewer_id
            review.review_note = note
            # Columns are TIMESTAMP WITHOUT TIME ZONE: store naive UTC.
            # An offset-aware value fails on PostgreSQL (asyncpg DataError)
            # while SQLite silently accepts it.
            review.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            crew.publication_status = "approved"
            document.extraction_status = "approved"
            approved_document_ids = list(
                (
                    await session.execute(
                        select(Document.id).where(
                            Document.crew_member_id == crew_id,
                            Document.extraction_status.in_({"approved", "extracted"}),
                        )
                    )
                ).scalars()
            )
            await session.commit()
            await session.refresh(crew)

        for cache_key in (
            cache_service._make_key("summary", crew_id),
            cache_service._make_key("compliance", crew_id),
        ):
            try:
                await cache_service.delete(cache_key)
            except Exception as exc:
                logger.warning("Could not clear approved CV cache (%s)", type(exc).__name__)
        await _repair_crew_projection(crew)
        await _repair_document_projection(document_id)
        # Approval is the publication transition for a CV. If semantic search
        # is enabled, queue the document projection now; extraction correctly
        # skipped it while the review was still awaiting a decision.
        from app.tasks.document_tasks import _maybe_queue_embeddings

        for approved_document_id in approved_document_ids:
            _maybe_queue_embeddings(approved_document_id, "approved")
            await _repair_document_projection(approved_document_id)
        return review

    async def reject(self, review_id: str, *, reviewer_id: str, note: str) -> CVReview:
        if not isinstance(note, str):
            raise ValueError("Review note must be a string")
        if len(note) > MAX_REVIEW_NOTE_LENGTH:
            raise ValueError(
                f"Review note is too large (max {MAX_REVIEW_NOTE_LENGTH} characters)"
            )
        factory = get_session_factory()
        async with factory() as session:
            review = (
                await session.execute(select(CVReview).where(CVReview.id == review_id))
            ).scalar_one_or_none()
            if review is None:
                raise ValueError("CV review not found")
            if review.status == "rejected":
                # Retry all derived-state cleanup, not only the semantic
                # vector. The first rejection may have completed in
                # PostgreSQL while Meilisearch was unavailable.
                from app.services.crew import crew_service

                crew = await crew_service.get_crew_member(review.crew_member_id)
                if crew is not None:
                    await _repair_crew_projection(crew)
                # Idempotent retries must still repair derived projections if
                # the first cleanup ran while a provider was unavailable.
                await _repair_document_vector(review.document_id)
                for cache_key in (
                    cache_service._make_key("summary", review.crew_member_id),
                    cache_service._make_key("compliance", review.crew_member_id),
                ):
                    try:
                        await cache_service.delete(cache_key)
                    except Exception as exc:
                        logger.warning("Could not clear rejected CV cache (%s)", type(exc).__name__)
                await _repair_document_projection(review.document_id)
                return review
            document = (
                await session.execute(
                    select(Document).where(Document.id == review.document_id).with_for_update()
                )
            ).scalar_one_or_none()
            if document is None:
                raise ValueError("CV document not found")
            review = (
                await session.execute(
                    select(CVReview).where(CVReview.id == review_id).with_for_update()
                )
            ).scalar_one()
            if review.status != "awaiting_review":
                raise ValueError("CV review is not awaiting a decision")
            if document.extraction_status != "awaiting_review":
                raise ValueError("CV document is no longer awaiting a decision")
            review.status = "rejected"
            review.reviewed_by = reviewer_id
            review.review_note = note
            # Columns are TIMESTAMP WITHOUT TIME ZONE: store naive UTC.
            # An offset-aware value fails on PostgreSQL (asyncpg DataError)
            # while SQLite silently accepts it.
            review.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            crew = (
                await session.execute(
                    select(CrewMember)
                    .where(CrewMember.id == review.crew_member_id)
                    .with_for_update()
                )
            ).scalar_one()
            if document.crew_member_id != review.crew_member_id:
                raise ValueError("CV document does not belong to this contractor")
            if not is_contractor_profile(crew):
                raise ValueError("Crew member not found")
            crew.publication_status = (
                "approved" if review.prior_publication_status == "approved" else "rejected"
            )
            document.extraction_status = "rejected"
            await session.commit()
            await session.refresh(crew)
        if crew.publication_status == "approved":
            await _repair_crew_projection(crew)
        else:
            await _repair_crew_projection(crew)
        # A replacement CV may already have an embedding from the previous
        # approved extraction. Rejection changes the document to a
        # non-searchable state, so remove that stale semantic projection even
        # when the contractor profile itself remains published.
        await _repair_document_vector(review.document_id)
        await _repair_document_projection(review.document_id)
        return review


cv_review_service = CVReviewService()
