"""Provider-free contractor document request and review-queue use cases."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import get_settings
from app.database import get_session_factory
from app.models import CrewMember, Document, DocumentRequest, IncomingDocumentReview


@dataclass(frozen=True)
class CreatedDocumentRequest:
    token: str
    expires_at: datetime
    request_id: str


class DocumentRequestService:
    """Owns token validation and durable review-queue state."""

    @staticmethod
    def _token_hash(token: str) -> str:
        return hmac.new(
            get_settings().SESSION_SECRET_KEY.encode(), token.encode(), hashlib.sha256
        ).hexdigest()

    async def create(
        self,
        *,
        crew_id: str,
        actor_id: str,
        actor_role: str = "staff",
        expires_in_days: int,
    ) -> CreatedDocumentRequest:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        naive_expires_at = (
            expires_at.astimezone(timezone.utc).replace(tzinfo=None)
            if expires_at.tzinfo
            else expires_at
        )
        async with get_session_factory()() as session:
            crew = (
                await session.execute(select(CrewMember).where(CrewMember.id == crew_id))
            ).scalar_one_or_none()
            if crew is None:
                raise ValueError("Contractor not found")
            if crew.publication_status == "rejected":
                raise ValueError("Cannot request documents for a rejected contractor")
            if actor_role != "admin" and crew.publication_status != "approved":
                if crew.submitted_by != actor_id:
                    raise PermissionError("This draft belongs to another user")
            req = DocumentRequest(
                crew_member_id=crew.id,
                token_hash=self._token_hash(token),
                expires_at=naive_expires_at,
                created_by=actor_id,
            )
            session.add(req)
            await session.commit()
            req_id = req.id
        return CreatedDocumentRequest(token=token, expires_at=expires_at, request_id=req_id)

    async def get_active_request(self, token: str) -> DocumentRequest | None:
        if not token or len(token) > 256 or not re.fullmatch(r"[A-Za-z0-9_-]{20,128}", token):
            return None
        async with get_session_factory()() as session:
            request = (
                await session.execute(
                    select(DocumentRequest).where(
                        DocumentRequest.token_hash == self._token_hash(token)
                    )
                )
            ).scalar_one_or_none()
            if request is None or request.status != "active":
                return None
            expires_at = request.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                request.status = "expired"
                await session.commit()
                return None
            session.expunge(request)
            request.expires_at = expires_at
            return request

    async def create_review(self, *, request_id: str, document_id: str) -> None:
        async with get_session_factory()() as session:
            session.add(IncomingDocumentReview(request_id=request_id, document_id=document_id))
            await session.commit()

    async def resolve_review(
        self,
        *,
        review_id: str | None = None,
        document_id: str | None = None,
        actor_id: str,
        actor_role: str = "staff",
        action: str,
        note: str | None = None,
    ) -> tuple[IncomingDocumentReview | None, Document]:
        """Approve or reject a document, resolving any active review-queue item."""
        if action not in ("approve", "reject"):
            raise ValueError(f"Invalid action: '{action}'. Must be 'approve' or 'reject'.")
        if not review_id and not document_id:
            raise ValueError("Either review_id or document_id must be provided.")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with get_session_factory()() as session:
            review: IncomingDocumentReview | None = None
            if review_id:
                stmt = (
                    select(IncomingDocumentReview, Document, CrewMember)
                    .join(Document, IncomingDocumentReview.document_id == Document.id)
                    .join(CrewMember, Document.crew_member_id == CrewMember.id)
                    .where(IncomingDocumentReview.id == review_id)
                )
                row = (await session.execute(stmt)).first()
                if row is None:
                    raise ValueError("Review item not found")
                review, doc, crew = row
            else:
                stmt_doc = (
                    select(Document, CrewMember)
                    .join(CrewMember, Document.crew_member_id == CrewMember.id)
                    .where(Document.id == document_id)
                )
                row_doc = (await session.execute(stmt_doc)).first()
                if row_doc is None:
                    raise ValueError("Document not found")
                doc, crew = row_doc
                review = (
                    await session.execute(
                        select(IncomingDocumentReview).where(
                            IncomingDocumentReview.document_id == doc.id
                        )
                    )
                ).scalar_one_or_none()

            if review is not None and review.status not in ("unread", "claimed"):
                raise ValueError(f"Review item has already been resolved ({review.status})")

            if actor_role != "admin" and crew.publication_status != "approved":
                if crew.submitted_by != actor_id:
                    raise PermissionError("This contractor draft belongs to another user")

            if review is not None:
                review.claimed_by = actor_id
                review.resolved_at = now
                review.status = "resolved" if action == "approve" else "rejected"

            doc.extraction_status = "approved" if action == "approve" else "rejected"
            await session.commit()
            if review is not None:
                session.expunge(review)
            session.expunge(doc)

        from app.services.audit import audit_service

        await audit_service.log_access(
            document_id=doc.id,
            user_id=actor_id,
            action=f"review_{action}",
            details={"review_id": review.id if review else None, "note": note},
        )
        return review, doc


document_request_service = DocumentRequestService()
