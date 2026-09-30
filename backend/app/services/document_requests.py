"""Provider-free contractor document request and review-queue use cases."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from app.config import get_settings
from app.database import get_session_factory
from app.domain.crew_accounts import is_contractor_profile
from app.domain.fields import normalize_classification
from app.domain.input_limits import MAX_REVIEW_NOTE_LENGTH
from app.models import Certification, CrewMember, Document, DocumentRequest, IncomingDocumentReview
from app.services.cache import cache_service

logger = logging.getLogger(__name__)


async def _log_review_audit_best_effort(
    *,
    document_id: str,
    actor_id: str,
    action: str,
    review_id: str | None,
    note: str | None,
) -> None:
    """Keep a committed review decision authoritative during audit outages."""
    try:
        from app.services.audit import audit_service

        await audit_service.log_access(
            document_id=document_id,
            user_id=actor_id,
            action=action,
            details={"review_id": review_id, "note": note},
        )
    except Exception as exc:
        logger.warning("Could not record review audit (%s)", type(exc).__name__)


@dataclass(frozen=True)
class CreatedDocumentRequest:
    token: str
    expires_at: datetime
    request_id: str


def _mark_review_resolved(
    review: IncomingDocumentReview,
    *,
    actor_id: str,
    action: str,
    now: datetime,
) -> None:
    """Record the first claim and terminal decision for a review item."""
    review.claimed_by = actor_id
    review.claimed_at = review.claimed_at or now
    review.resolved_at = now
    review.status = "resolved" if action == "approve" else "rejected"


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
        if (
            not isinstance(expires_in_days, int)
            or isinstance(expires_in_days, bool)
            or not 1 <= expires_in_days <= 30
        ):
            raise ValueError("Expiry must be between 1 and 30 days")
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        naive_expires_at = (
            expires_at.astimezone(timezone.utc).replace(tzinfo=None)
            if expires_at.tzinfo
            else expires_at
        )
        async with get_session_factory()() as session:
            crew = (
                await session.execute(
                    select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
                )
            ).scalar_one_or_none()
            if crew is None:
                raise ValueError("Contractor not found")
            if not is_contractor_profile(crew):
                raise ValueError("Contractor not found")
            if crew.publication_status == "rejected":
                raise ValueError("Cannot request documents for a rejected contractor")
            if actor_role != "admin" and crew.publication_status != "approved":
                if crew.publication_status != "draft" or crew.submitted_by != actor_id:
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
                    select(DocumentRequest)
                    .join(CrewMember, DocumentRequest.crew_member_id == CrewMember.id)
                    .where(
                        DocumentRequest.token_hash == self._token_hash(token),
                        CrewMember.publication_status != "rejected",
                        CrewMember.password_hash.is_(None),
                        or_(
                            CrewMember.role.is_(None),
                            CrewMember.role.not_in(("staff", "admin")),
                        ),
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
            request = (
                await session.execute(
                    select(DocumentRequest)
                    .join(CrewMember, DocumentRequest.crew_member_id == CrewMember.id)
                    .where(DocumentRequest.id == request_id)
                    .where(
                        CrewMember.password_hash.is_(None),
                        or_(
                            CrewMember.role.is_(None),
                            CrewMember.role.not_in(("staff", "admin")),
                        ),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if request is None:
                raise ValueError("Document request not found")
            if request.status != "active":
                raise ValueError("Document request is not active")
            expires_at = request.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise ValueError("Document request has expired")

            document = (
                await session.execute(
                    select(Document).where(Document.id == document_id).with_for_update()
                )
            ).scalar_one_or_none()
            if document is None:
                raise ValueError("Document not found")
            if document.crew_member_id != request.crew_member_id:
                raise ValueError("Document does not belong to the requested contractor")
            crew = (
                await session.execute(
                    select(CrewMember)
                    .where(CrewMember.id == request.crew_member_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if crew is None or not is_contractor_profile(crew):
                raise ValueError("Contractor not found")
            existing = (
                await session.execute(
                    select(IncomingDocumentReview).where(
                        IncomingDocumentReview.document_id == document_id
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise ValueError("Document already has a review item")
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
        if note is not None and not isinstance(note, str):
            raise ValueError("Review note must be a string")
        if note is not None and len(note) > MAX_REVIEW_NOTE_LENGTH:
            raise ValueError(f"Review note is too large (max {MAX_REVIEW_NOTE_LENGTH} characters)")
        if not review_id and not document_id:
            raise ValueError("Either review_id or document_id must be provided.")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        approved_certificate_data: dict[str, object] | None = None
        approved_certificate_crew_id: str | None = None
        approved_certificate_document_id: str | None = None
        approved_review_resolved_at: datetime | None = None
        async with get_session_factory()() as session:
            review: IncomingDocumentReview | None = None
            if review_id:
                review = (
                    await session.execute(
                        select(IncomingDocumentReview).where(IncomingDocumentReview.id == review_id)
                    )
                ).scalar_one_or_none()
                if review is None:
                    raise ValueError("Review item not found")
                document_id = review.document_id
            else:
                if document_id is None:
                    raise ValueError("Either review_id or document_id must be provided.")
                document_exists = await session.get(Document, document_id)
                if document_exists is None:
                    raise ValueError("Document not found")

            # Dropbox revision processing locks the document before updating
            # its review row. Keep the same order here to avoid a
            # document/review deadlock during concurrent review and revision.
            doc = (
                await session.execute(
                    select(Document).where(Document.id == document_id).with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                raise ValueError("Document not found")
            # Serialize against an extraction worker's terminal-state check so
            # a late worker cannot overwrite this human decision. Keep the
            # lock order document -> contractor -> review, matching the
            # extraction and ingestion paths.
            if not doc.crew_member_id:
                raise ValueError("Contractor not found")
            crew = (
                await session.execute(
                    select(CrewMember).where(CrewMember.id == doc.crew_member_id).with_for_update()
                )
            ).scalar_one_or_none()
            if crew is None:
                raise ValueError("Contractor not found")
            if not is_contractor_profile(crew):
                raise ValueError("Contractor not found")

            review_stmt = select(IncomingDocumentReview).with_for_update()
            if review_id:
                review_stmt = review_stmt.where(IncomingDocumentReview.id == review_id)
            else:
                review_stmt = review_stmt.where(IncomingDocumentReview.document_id == doc.id)
            review = (await session.execute(review_stmt)).scalar_one_or_none()
            if review_id and review is None:
                raise ValueError("Review item not found")

            # Authorize ownership before revealing review/document state. A
            # staff member must not learn whether another user's draft is
            # pending, approved, or rejected from a state-specific error.
            if actor_role != "admin" and crew.publication_status != "approved":
                if crew.publication_status != "draft" or crew.submitted_by != actor_id:
                    raise PermissionError("This contractor draft belongs to another user")

            if review is not None and review.status not in ("unread", "claimed"):
                # Preserve the terminal-decision error, but make repeated
                # rejection attempts useful: the first cleanup may have run
                # while a derived provider was unavailable. Approved retries
                # also repair the projection after a committed decision.
                if review.status == "rejected":
                    if get_settings().ENABLE_SEMANTIC_SEARCH:
                        from app.services.qdrant import qdrant_service

                        try:
                            if not await qdrant_service.delete_document(doc.id):
                                from app.tasks.document_tasks import (
                                    queue_document_projection_cleanup,
                                )

                                queue_document_projection_cleanup(doc.id)
                        except Exception as exc:
                            logger.warning(
                                "Could not retry rejected document vector cleanup (%s)",
                                type(exc).__name__,
                            )
                            from app.tasks.document_tasks import queue_document_projection_cleanup

                            queue_document_projection_cleanup(doc.id)
                    from app.services.consultant_knowledge import consultant_knowledge_service

                    try:
                        if not await consultant_knowledge_service.reconcile_document_index(doc.id):
                            from app.tasks.document_tasks import queue_document_search_reconcile

                            queue_document_search_reconcile(doc.id)
                    except Exception as exc:
                        logger.warning(
                            "Could not retry rejected document projection (%s)", type(exc).__name__
                        )
                        from app.tasks.document_tasks import queue_document_search_reconcile

                        queue_document_search_reconcile(doc.id)
                    raise ValueError(f"Review item has already been resolved ({review.status})")
                if (
                    review.status == "resolved"
                    and action == "approve"
                    and doc.extraction_status == "approved"
                ):
                    from app.services.consultant_knowledge import consultant_knowledge_service

                    try:
                        if not await consultant_knowledge_service.reconcile_document_index(doc.id):
                            from app.tasks.document_tasks import queue_document_search_reconcile

                            queue_document_search_reconcile(doc.id)
                    except Exception as exc:
                        logger.warning(
                            "Could not retry approved document projection (%s)",
                            type(exc).__name__,
                        )
                        from app.tasks.document_tasks import queue_document_search_reconcile

                        queue_document_search_reconcile(doc.id)
                    if normalize_classification(doc.classification) == "certificate" and isinstance(
                        doc.extracted_data, dict
                    ):
                        # A previous approval may have committed before its
                        # certificate projection succeeded. Keep repeated
                        # approval idempotent, but make it a repair trigger too.
                        from app.tasks.document_tasks import (
                            queue_certificate_projection_reconcile,
                        )

                        queue_certificate_projection_reconcile(doc.id)
                    from app.tasks.document_tasks import _maybe_queue_embeddings

                    _maybe_queue_embeddings(doc.id, "approved")
                    for cache_key in (
                        cache_service._make_key("compliance", crew.id),
                        cache_service._make_key("summary", crew.id),
                    ):
                        try:
                            await cache_service.delete(cache_key)
                        except Exception as exc:
                            logger.warning(
                                "Could not clear repeated approval cache (%s)", type(exc).__name__
                            )
                    session.expunge(review)
                    session.expunge(doc)
                    return review, doc
                raise ValueError(f"Review item has already been resolved ({review.status})")

            if doc.extraction_status in {"approved", "rejected"}:
                raise ValueError(
                    f"Document decision has already been resolved ({doc.extraction_status})"
                )

            if normalize_classification(doc.classification) == "cv":
                raise ValueError(
                    "CV documents must be resolved through the administrator CV review workflow"
                )

            if action == "approve" and doc.extraction_status not in {"extracted", "needs_review"}:
                raise ValueError(
                    "Document extraction is not ready for approval; wait for extraction to finish"
                )

            if actor_role != "admin" and (
                review is None or doc.uploaded_by != "contractor-upload-link"
            ):
                raise PermissionError("Document is not an active contractor-upload review")

            if review is not None:
                _mark_review_resolved(review, actor_id=actor_id, action=action, now=now)

            if action == "reject":
                linked_certifications = await session.execute(
                    select(Certification).where(Certification.document_ref == doc.id)
                )
                detached_certification_ids: list[str] = []
                detached_expiry_dates = []
                for certification in linked_certifications.scalars():
                    detached_certification_ids.append(certification.id)
                    detached_expiry_dates.append(certification.expiry_date)
                    certification.document_ref = None
                    certification.verification_status = "unverified"
                    if certification.status != "expired":
                        certification.status = "pending_verification"
                from app.services.certification_projection import (
                    reconcile_medical_profile_after_detachment,
                )

                await reconcile_medical_profile_after_detachment(
                    session,
                    crew_id=crew.id,
                    detached_certification_ids=detached_certification_ids,
                    detached_expiry_dates=detached_expiry_dates,
                )

            doc.extraction_status = "approved" if action == "approve" else "rejected"
            if (
                action == "approve"
                and normalize_classification(doc.classification) == "certificate"
                and isinstance(doc.extracted_data, dict)
            ):
                # The linker owns certificate normalization and matching. Run it
                # after this source-of-truth approval commits because its public
                # API opens its own transaction and intentionally accepts only
                # extracted/approved documents.
                approved_certificate_data = dict(doc.extracted_data)
                approved_certificate_crew_id = crew.id
                approved_certificate_document_id = doc.id
            await session.commit()
            approved_review_resolved_at = review.resolved_at if review is not None else None
            if review is not None:
                session.expunge(review)
            session.expunge(doc)

        if (
            approved_certificate_data is not None
            and approved_certificate_crew_id is not None
            and approved_certificate_document_id is not None
        ):
            from app.services.crew import certification_service

            try:
                await certification_service.link_extracted_certificate(
                    crew_id=approved_certificate_crew_id,
                    document_id=approved_certificate_document_id,
                    extracted_data=approved_certificate_data,
                )
            except Exception as exc:
                logger.error(
                    "Certificate projection failed after document approval (%s)",
                    type(exc).__name__,
                    extra={"document_id": approved_certificate_document_id},
                )
                # The document decision was committed before the projection
                # service opened its own transaction. Reopen the review and
                # make the evidence non-searchable so a transient projection
                # failure cannot strand an approved document that has no
                # durable certification projection.
                try:
                    async with get_session_factory()() as recovery_session:
                        recovery_doc = (
                            await recovery_session.execute(
                                select(Document)
                                .where(Document.id == approved_certificate_document_id)
                                .with_for_update()
                            )
                        ).scalar_one_or_none()
                        if (
                            recovery_doc is not None
                            and recovery_doc.extraction_status == "approved"
                        ):
                            recovery_review = (
                                await recovery_session.execute(
                                    select(IncomingDocumentReview)
                                    .where(IncomingDocumentReview.document_id == recovery_doc.id)
                                    .with_for_update()
                                )
                            ).scalar_one_or_none()
                            if recovery_review is not None and (
                                recovery_review.status != "resolved"
                                or approved_review_resolved_at is None
                                or recovery_review.resolved_at != approved_review_resolved_at
                            ):
                                raise RuntimeError("Skipping stale certificate projection recovery")
                            if recovery_review is None and approved_review_resolved_at is not None:
                                raise RuntimeError("Skipping stale certificate projection recovery")
                            linked_certifications = await recovery_session.execute(
                                select(Certification).where(
                                    Certification.document_ref == recovery_doc.id
                                )
                            )
                            detached_ids: list[str] = []
                            detached_expiry_dates = []
                            for certification in linked_certifications.scalars():
                                detached_ids.append(certification.id)
                                detached_expiry_dates.append(certification.expiry_date)
                                certification.document_ref = None
                                certification.verification_status = "unverified"
                                if certification.status != "expired":
                                    certification.status = "pending_verification"
                            from app.services.certification_projection import (
                                reconcile_medical_profile_after_detachment,
                            )

                            await reconcile_medical_profile_after_detachment(
                                recovery_session,
                                crew_id=approved_certificate_crew_id,
                                detached_certification_ids=detached_ids,
                                detached_expiry_dates=detached_expiry_dates,
                            )
                            recovery_doc.extraction_status = "needs_review"
                            if recovery_review is not None:
                                recovery_review.status = "unread"
                                recovery_review.claimed_by = None
                                recovery_review.claimed_at = None
                                recovery_review.resolved_at = None
                            await recovery_session.commit()
                            for cache_key in (
                                cache_service._make_key("compliance", approved_certificate_crew_id),
                                cache_service._make_key("summary", approved_certificate_crew_id),
                            ):
                                try:
                                    await cache_service.delete(cache_key)
                                except Exception as exc:
                                    logger.warning(
                                        "Could not clear recovered review cache (%s)",
                                        type(exc).__name__,
                                    )
                            if get_settings().ENABLE_SEMANTIC_SEARCH:
                                from app.services.qdrant import qdrant_service

                                try:
                                    vector_deleted = await qdrant_service.delete_document(
                                        approved_certificate_document_id
                                    )
                                except Exception as exc:
                                    logger.warning(
                                        "Could not remove recovered document vector (%s)",
                                        type(exc).__name__,
                                    )
                                    from app.tasks.document_tasks import (
                                        queue_document_projection_cleanup,
                                    )

                                    queue_document_projection_cleanup(
                                        approved_certificate_document_id
                                    )
                                else:
                                    if not vector_deleted:
                                        from app.tasks.document_tasks import (
                                            queue_document_projection_cleanup,
                                        )

                                        queue_document_projection_cleanup(
                                            approved_certificate_document_id
                                        )
                            from app.services.consultant_knowledge import (
                                consultant_knowledge_service,
                            )

                            try:
                                search_reconciled = (
                                    await consultant_knowledge_service.reconcile_document_index(
                                        approved_certificate_document_id
                                    )
                                )
                            except Exception as exc:
                                logger.warning(
                                    "Could not reconcile recovered document projection (%s)",
                                    type(exc).__name__,
                                )
                                from app.tasks.document_tasks import queue_document_search_reconcile

                                queue_document_search_reconcile(approved_certificate_document_id)
                            else:
                                if not search_reconciled:
                                    from app.tasks.document_tasks import (
                                        queue_document_search_reconcile,
                                    )

                                    queue_document_search_reconcile(
                                        approved_certificate_document_id
                                    )
                except Exception as exc:
                    # Preserve the original projection error while making the
                    # recovery failure observable for operators.
                    logger.error(
                        "Could not reopen document review after projection failure (%s)",
                        type(exc).__name__,
                        extra={"document_id": approved_certificate_document_id},
                    )
                raise

        from app.services.consultant_knowledge import consultant_knowledge_service

        try:
            if not await consultant_knowledge_service.reconcile_document_index(doc.id):
                from app.tasks.document_tasks import queue_document_search_reconcile

                queue_document_search_reconcile(doc.id)
        except Exception as exc:
            logger.warning(
                "Could not reconcile reviewed document projection (%s)", type(exc).__name__
            )
            from app.tasks.document_tasks import queue_document_search_reconcile

            queue_document_search_reconcile(doc.id)

        await _log_review_audit_best_effort(
            document_id=doc.id,
            actor_id=actor_id,
            action=f"review_{action}",
            review_id=review.id if review else None,
            note=note,
        )
        for cache_key in (
            cache_service._make_key("compliance", crew.id),
            cache_service._make_key("summary", crew.id),
        ):
            try:
                await cache_service.delete(cache_key)
            except Exception as exc:
                # The source decision and search reconciliation already
                # committed. Do not let a Redis outage skip vector cleanup or
                # approved embedding dispatch below.
                logger.warning("Could not clear review cache (%s)", type(exc).__name__)
        if action == "reject" and get_settings().ENABLE_SEMANTIC_SEARCH:
            from app.services.qdrant import qdrant_service

            try:
                if not await qdrant_service.delete_document(doc.id):
                    from app.tasks.document_tasks import queue_document_projection_cleanup

                    queue_document_projection_cleanup(doc.id)
            except Exception as exc:
                logger.warning("Could not remove rejected document vector (%s)", type(exc).__name__)
                from app.tasks.document_tasks import queue_document_projection_cleanup

                queue_document_projection_cleanup(doc.id)
        elif action == "approve":
            # Contractor uploads are intentionally skipped by the extraction
            # worker's embedding task until this human decision. Queue the
            # approved source now so enabling semantic search does not leave
            # accepted contractor evidence permanently absent from Qdrant.
            from app.tasks.document_tasks import _maybe_queue_embeddings

            _maybe_queue_embeddings(doc.id, "approved")
        return review, doc


document_request_service = DocumentRequestService()
