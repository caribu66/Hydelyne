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
from app.models import CrewMember, DocumentRequest, IncomingDocumentReview


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
                expires_at=expires_at,
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
            return request

    async def create_review(self, *, request_id: str, document_id: str) -> None:
        async with get_session_factory()() as session:
            session.add(IncomingDocumentReview(request_id=request_id, document_id=document_id))
            await session.commit()


document_request_service = DocumentRequestService()
