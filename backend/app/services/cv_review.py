"""Application service for staged, administrator-reviewed CV ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_session_factory
from app.models import CrewMember, CVReview, Document
from app.services.cache import cache_service
from app.services.consultant_knowledge import consultant_knowledge_service
from app.services.cv_processing import cv_processing_service


class CVReviewService:
    async def list_visible(
        self,
        *,
        actor_id: str,
        actor_role: str,
        limit: int,
        offset: int,
    ) -> list[CVReview]:
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CVReview).order_by(CVReview.created_at.desc())
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
        factory = get_session_factory()
        async with factory() as session:
            review = (
                await session.execute(
                    select(CVReview).where(CVReview.id == review_id).with_for_update()
                )
            ).scalar_one_or_none()
            if review is None:
                raise ValueError("CV review not found")
            if review.status == "approved":
                return review
            if review.status != "awaiting_review":
                raise ValueError("CV review is not awaiting approval")
            crew_id = review.crew_member_id
            document_id = review.document_id
            crew = (
                await session.execute(
                    select(CrewMember)
                    .options(
                        selectinload(CrewMember.certifications),
                        selectinload(CrewMember.work_history),
                    )
                    .where(CrewMember.id == crew_id)
                )
            ).scalar_one()
            document = (
                await session.execute(select(Document).where(Document.id == document_id))
            ).scalar_one()
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
            review.reviewed_at = datetime.now(timezone.utc)
            crew.publication_status = "approved"
            document.extraction_status = "approved"
            await session.commit()
            await session.refresh(crew)

        await cache_service.delete(cache_service._make_key("summary", crew_id))
        await consultant_knowledge_service.index_crew_member(crew)
        return review

    async def reject(self, review_id: str, *, reviewer_id: str, note: str) -> CVReview:
        factory = get_session_factory()
        async with factory() as session:
            review = (
                await session.execute(
                    select(CVReview).where(CVReview.id == review_id).with_for_update()
                )
            ).scalar_one_or_none()
            if review is None:
                raise ValueError("CV review not found")
            if review.status == "rejected":
                return review
            if review.status != "awaiting_review":
                raise ValueError("CV review is not awaiting a decision")
            review.status = "rejected"
            review.reviewed_by = reviewer_id
            review.review_note = note
            review.reviewed_at = datetime.now(timezone.utc)
            crew = (
                await session.execute(
                    select(CrewMember).where(CrewMember.id == review.crew_member_id)
                )
            ).scalar_one()
            crew.publication_status = (
                "approved" if review.prior_publication_status == "approved" else "rejected"
            )
            document = (
                await session.execute(select(Document).where(Document.id == review.document_id))
            ).scalar_one()
            document.extraction_status = "rejected"
            await session.commit()
            await session.refresh(crew)
        if crew.publication_status == "approved":
            await consultant_knowledge_service.index_crew_member(crew)
        else:
            await consultant_knowledge_service.remove_from_index(crew.id)
        return review


cv_review_service = CVReviewService()
