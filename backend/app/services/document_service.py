from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, or_, select

from app.database import get_session_factory
from app.domain.crew_accounts import is_contractor_profile
from app.domain.document_processing import processing_claim_is_stale
from app.domain.fields import CV_UPLOADERS_REQUIRING_REJECTION, normalize_classification
from app.domain.input_limits import validate_pagination
from app.models import Certification, CrewMember, IncomingDocumentReview
from app.models import Document as DocumentModel
from app.services.audit import audit_service
from app.services.cache import cache_service
from app.services.extraction import extraction_service
from app.services.text_extraction import text_extraction_service
from app.services.upload import (
    MAX_FILE_SIZE,
    MAX_FILENAME_LENGTH,
    document_upload_service,
    is_managed_dropbox_path,
)

logger = logging.getLogger(__name__)


def _validate_document_metadata(
    file_name: str,
    file_type: str,
    file_size: int,
    storage_path: str,
    uploaded_by: str | None,
) -> None:
    """Validate document metadata before constructing a persistent row."""
    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("file_name must not be empty")
    if len(file_name) > MAX_FILENAME_LENGTH:
        raise ValueError(f"file_name must be {MAX_FILENAME_LENGTH} characters or fewer")
    if not isinstance(file_type, str) or not file_type.strip():
        raise ValueError("file_type must not be empty")
    if len(file_type) > 50:
        raise ValueError("file_type must be 50 characters or fewer")
    if not isinstance(file_size, int) or isinstance(file_size, bool) or not 0 < file_size <= MAX_FILE_SIZE:
        raise ValueError(f"file_size must be between 1 and {MAX_FILE_SIZE} bytes")
    if not isinstance(storage_path, str) or not storage_path or len(storage_path) > 500:
        raise ValueError("storage_path must be between 1 and 500 characters")
    if storage_path.startswith("/hydenlyne/") and not is_managed_dropbox_path(storage_path):
        raise ValueError("storage_path is not a managed Dropbox path")
    if uploaded_by is not None and (
        not isinstance(uploaded_by, str) or len(uploaded_by) > 255
    ):
        raise ValueError("uploaded_by must be 255 characters or fewer")


async def _log_extraction_best_effort(
    document_id: str,
    *,
    model_used: str,
    confidence: dict,
    status: str,
) -> None:
    """Record extraction history without changing a committed outcome."""
    try:
        await audit_service.log_extraction(
            document_id=document_id,
            model_used=model_used,
            confidence=confidence,
            status=status,
        )
    except Exception as exc:
        # The document and any derived certification were committed before
        # audit persistence. An audit outage must not turn that success into a
        # retryable extraction failure or overwrite it with ``failed``.
        logger.warning("Could not record extraction audit (%s)", type(exc).__name__)


async def _log_access_best_effort(
    document_id: str,
    *,
    user_id: str,
    action: str,
    data_keys: list[str],
) -> None:
    """Record post-commit access history without changing the mutation result."""
    try:
        await audit_service.log_access(
            document_id=document_id,
            user_id=user_id,
            action=action,
            data_keys=data_keys,
        )
    except Exception as exc:
        logger.warning("Could not record document access audit (%s)", type(exc).__name__)


async def _cleanup_failed_document_projections(document_id: str) -> None:
    """Remove derived projections without masking a committed failure state."""
    from app.config import get_settings

    if get_settings().ENABLE_SEMANTIC_SEARCH:
        from app.services.qdrant import qdrant_service

        try:
            if not await qdrant_service.delete_document(document_id):
                from app.tasks.document_tasks import queue_document_projection_cleanup

                queue_document_projection_cleanup(document_id)
        except Exception as exc:
            logger.warning("Could not remove failed document vector (%s)", type(exc).__name__)
            from app.tasks.document_tasks import queue_document_projection_cleanup

            queue_document_projection_cleanup(document_id)

    from app.services.consultant_knowledge import consultant_knowledge_service

    try:
        if not await consultant_knowledge_service.reconcile_document_index(document_id):
            from app.tasks.document_tasks import queue_document_search_reconcile

            queue_document_search_reconcile(document_id)
    except Exception as exc:
        logger.warning("Could not reconcile failed document projection (%s)", type(exc).__name__)
        from app.tasks.document_tasks import queue_document_search_reconcile

        queue_document_search_reconcile(document_id)


class DocumentService:
    """Service for document operations."""

    async def create_document(
        self,
        crew_id: str,
        file_name: str,
        file_type: str,
        file_size: int,
        storage_path: str,
        classification: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> DocumentModel:
        """Create a document record in the database."""
        if classification is not None and not isinstance(classification, str):
            raise ValueError("classification must be a string")
        _validate_document_metadata(file_name, file_type, file_size, storage_path, uploaded_by)
        factory = get_session_factory()
        async with factory() as session:
            crew = (
                await session.execute(
                    select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
                )
            ).scalar_one_or_none()
            if crew is None or not is_contractor_profile(crew):
                raise ValueError("Crew member not found")
            doc = DocumentModel(
                crew_member_id=crew_id,
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                storage_type="dropbox" if storage_path.startswith("/hydenlyne/") else "local",
                storage_path=storage_path,
                dropbox_path=storage_path if storage_path.startswith("/hydenlyne/") else None,
                classification=normalize_classification(classification),
                uploaded_by=uploaded_by,
                extraction_status="pending",
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)
            return doc

    async def get_document(self, document_id: str) -> Optional[DocumentModel]:
        """Get a document by ID."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_documents_by_crew(
        self, crew_id: str, limit: int = 50, offset: int = 0
    ) -> list[DocumentModel]:
        """Get all documents belonging to a crew member."""
        limit, offset = validate_pagination(limit, offset)
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(DocumentModel)
                .where(DocumentModel.crew_member_id == crew_id)
                .order_by(DocumentModel.uploaded_at.desc(), DocumentModel.id.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def reprocess_document(self, document_id: str) -> DocumentModel:
        """Reset a document's extraction status so it's picked up again."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            if not doc:
                raise ValueError(f"Document {document_id} not found")
            if doc.crew_member_id:
                crew = await session.get(CrewMember, doc.crew_member_id)
                if crew is None or not is_contractor_profile(crew):
                    raise ValueError(f"Document {document_id} not found")
            if doc.extraction_status == "processing":
                raise ValueError("Document extraction is already in progress")

            was_searchable = doc.extraction_status in {"approved", "extracted"}
            detached_crew_id = doc.crew_member_id
            detached_certification_ids: list[str] = []
            if normalize_classification(doc.classification) == "certificate":
                linked_certifications = await session.execute(
                    select(Certification).where(Certification.document_ref == doc.id)
                )
                detached_expiry_dates = []
                for certification in linked_certifications.scalars():
                    detached_certification_ids.append(certification.id)
                    detached_expiry_dates.append(certification.expiry_date)
                    certification.document_ref = None
                    certification.verification_status = "unverified"
                    if certification.status != "expired":
                        certification.status = "pending_verification"
                if detached_crew_id:
                    from app.services.certification_projection import (
                        reconcile_medical_profile_after_detachment,
                    )

                    await reconcile_medical_profile_after_detachment(
                        session,
                        crew_id=detached_crew_id,
                        detached_certification_ids=detached_certification_ids,
                        detached_expiry_dates=detached_expiry_dates,
                    )

            if normalize_classification(doc.classification) == "cv":
                from app.models import CVReview

                review = (
                    await session.execute(
                        select(CVReview).where(CVReview.document_id == document_id)
                    )
                ).scalar_one_or_none()
                if review and review.status in {"approved", "rejected"}:
                    # Reprocessing is an explicit administrator action. Move a
                    # terminal review back into the workflow so the worker does
                    # not silently return the old decision without extracting.
                    review.status = "awaiting_review"
                    review.proposed_data = None
                    review.approved_data = None
                    review.reviewed_by = None
                    review.review_note = None
                    review.reviewed_at = None

            if doc.uploaded_by == "contractor-upload-link":
                # Reprocessing an already-approved contractor upload creates
                # new evidence that must pass through human review again. The
                # existing queue row is unique per document; reopen it rather
                # than creating a duplicate row that would violate that key.
                incoming_review = (
                    await session.execute(
                        select(IncomingDocumentReview).where(
                            IncomingDocumentReview.document_id == document_id
                        )
                    )
                ).scalar_one_or_none()
                if incoming_review is not None:
                    incoming_review.status = "unread"
                    incoming_review.claimed_by = None
                    incoming_review.claimed_at = None
                    incoming_review.resolved_at = None

            doc.extraction_status = "pending"
            doc.extracted_data = None
            doc.extracted_text = None
            doc.extraction_confidence = None
            await session.commit()
            await session.refresh(doc)
            from app.services.consultant_knowledge import consultant_knowledge_service

            if detached_crew_id:
                for cache_key in (
                    cache_service._make_key("compliance", detached_crew_id),
                    cache_service._make_key("summary", detached_crew_id),
                ):
                    try:
                        await cache_service.delete(cache_key)
                    except Exception as exc:
                        logger.warning("Could not clear reprocess cache (%s)", type(exc).__name__)
            try:
                if not await consultant_knowledge_service.reconcile_document_index(document_id):
                    from app.tasks.document_tasks import queue_document_search_reconcile

                    queue_document_search_reconcile(document_id)
            except Exception as exc:
                # Reprocessing must still be dispatched when a derived search
                # provider is temporarily unavailable. PostgreSQL is already
                # committed; the next successful reconciliation can repair
                # the projection after extraction completes.
                logger.warning(
                    "Could not reconcile reprocessed document projection (%s)",
                    type(exc).__name__,
                )
                from app.tasks.document_tasks import queue_document_search_reconcile

                queue_document_search_reconcile(document_id)
            finally:
                if was_searchable or detached_certification_ids:
                    from app.config import get_settings

                    if get_settings().ENABLE_SEMANTIC_SEARCH:
                        from app.services.qdrant import qdrant_service

                        try:
                            if not await qdrant_service.delete_document(document_id):
                                from app.tasks.document_tasks import (
                                    queue_document_projection_cleanup,
                                )

                                queue_document_projection_cleanup(document_id)
                        except Exception as exc:
                            logger.warning(
                                "Could not remove reprocessed document vector (%s)",
                                type(exc).__name__,
                            )
                            from app.tasks.document_tasks import queue_document_projection_cleanup

                            queue_document_projection_cleanup(document_id)
            try:
                from app.tasks.document_tasks import process_document_extraction

                process_document_extraction.delay(document_id)
            except Exception as exc:
                logger.warning(
                    "Could not queue reprocessed document extraction (%s)",
                    type(exc).__name__,
                )
                current = (
                    await session.execute(
                        select(DocumentModel)
                        .where(DocumentModel.id == document_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if current is not None and current.extraction_status == "pending":
                    current.extraction_status = "failed"
                    await session.commit()
                    await session.refresh(current)
                    doc = current
            return doc

    async def get_pending_documents(self, limit: int = 50, offset: int = 0) -> list[DocumentModel]:
        """Get all documents pending extraction."""
        limit, offset = validate_pagination(limit, offset)
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(DocumentModel)
                .outerjoin(CrewMember, DocumentModel.crew_member_id == CrewMember.id)
                .where(DocumentModel.extraction_status.in_(["pending", "failed", "needs_review"]))
                .where(
                    or_(
                        DocumentModel.crew_member_id.is_(None),
                        and_(
                            CrewMember.password_hash.is_(None),
                            or_(
                                CrewMember.role.is_(None),
                                CrewMember.role.not_in(("staff", "admin")),
                            ),
                        ),
                    )
                )
                .order_by(DocumentModel.uploaded_at.asc(), DocumentModel.id.asc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def process_document(self, document_id: str) -> dict:
        """Process a document through the extraction pipeline.

        Args:
            document_id: UUID of the document to process.

        Returns:
            Dict with extraction results.
        """
        was_approved_without_evidence = False
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return {"error": "Document not found", "status": "failed"}
            if doc.crew_member_id:
                from app.models import CrewMember as CrewMemberModel

                crew = (
                    await session.execute(
                        select(CrewMemberModel)
                        .where(CrewMemberModel.id == doc.crew_member_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if crew is None or not is_contractor_profile(crew):
                    doc.extraction_status = "rejected"
                    await session.commit()
                    await _cleanup_failed_document_projections(document_id)
                    return {
                        "document_id": document_id,
                        "status": "rejected",
                        "classification": normalize_classification(doc.classification),
                    }
            was_approved_without_evidence = bool(
                doc.extraction_status == "approved" and not doc.extracted_data
            )
            if doc.extraction_status == "rejected" or (
                doc.extraction_status == "approved" and not was_approved_without_evidence
            ):
                return {
                    "document_id": document_id,
                    "status": doc.extraction_status,
                    "classification": normalize_classification(doc.classification),
                }
            if doc.extraction_status == "processing":
                if not processing_claim_is_stale(doc.processing_started_at):
                    return {
                        "document_id": document_id,
                        "status": "processing",
                        "classification": normalize_classification(doc.classification),
                    }
                logger.warning("Recovering stale document extraction claim")
                doc.extraction_status = "pending"
            if (
                doc.extraction_status not in {"pending", "failed"}
                and not was_approved_without_evidence
            ):
                return {
                    "document_id": document_id,
                    "status": doc.extraction_status,
                    "classification": normalize_classification(doc.classification),
                }

            source_revision = doc.dropbox_revision
            doc.extraction_status = "processing"
            doc.processing_started_at = datetime.now(timezone.utc)
            await session.commit()

        try:
            is_image = text_extraction_service.is_image(doc.file_type)

            # Ensure file is available locally (download from Dropbox if needed)
            file_content = await document_upload_service.get_file_async(doc.storage_path)
            if file_content is None:
                raise FileNotFoundError("Managed document file is unavailable")
            valid, validation_error = document_upload_service.validate_file_content(
                doc.file_name, file_content
            )
            if not valid:
                raise ValueError(f"Stored document failed validation: {validation_error}")

            local_path = doc.storage_path
            if doc.storage_type == "dropbox" and doc.dropbox_path:
                # Update local_path to the cached file location
                cache_path = document_upload_service._get_local_cache_path(doc.dropbox_path)
                if cache_path:
                    local_path = str(cache_path)

            if is_image:
                doc.classification = normalize_classification(doc.classification or "certificate")
                extraction_result = await extraction_service.extract_from_image(
                    local_path, doc.classification or "certificate"
                )
            else:
                text = await text_extraction_service.extract_text(local_path, doc.file_type)

                if not doc.classification:
                    classification_result = await extraction_service.classify_document(text)
                    doc.classification = extraction_service.classification_from_result(
                        classification_result
                    )

                classification = normalize_classification(doc.classification)
                doc.classification = classification
                async with factory() as session:
                    stmt = (
                        select(DocumentModel)
                        .where(DocumentModel.id == document_id)
                        .with_for_update()
                    )
                    result = await session.execute(stmt)
                    db_doc = result.scalar_one_or_none()
                    if db_doc is None:
                        return {"error": "Document not found", "status": "failed"}
                    if db_doc.dropbox_revision != source_revision:
                        return {
                            "document_id": document_id,
                            "status": db_doc.extraction_status,
                            "classification": normalize_classification(db_doc.classification),
                        }
                    if db_doc.extraction_status in {"approved", "rejected"}:
                        return {
                            "document_id": document_id,
                            "status": db_doc.extraction_status,
                            "classification": normalize_classification(db_doc.classification),
                        }
                    db_doc.classification = classification
                    await session.commit()

                if classification == "cv":
                    # CVs never go through the LLM — see
                    # CVProcessingService.extract_cv_deterministically
                    # and backend/docs/consultant-knowledge-core.md.
                    from app.services.cv_processing import CVProcessingService

                    extraction_result = CVProcessingService.extract_cv_deterministically(
                        local_path, doc.file_type, text
                    )
                else:
                    extraction_result = await extraction_service.extract_document(
                        text=text,
                        document_type=classification,
                        is_image=False,
                    )

            review_status, needs_review = extraction_service.determine_review_status(
                extraction_result
            )

            terminal_status: str | None = None
            final_classification: str | None = None
            final_crew_member_id: str | None = None
            final_status: str | None = None
            async with factory() as session:
                stmt = (
                    select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
                )
                result = await session.execute(stmt)
                db_doc = result.scalar_one_or_none()
                if db_doc is None:
                    return {"error": "Document not found", "status": "failed"}
                if db_doc.dropbox_revision != source_revision:
                    return {
                        "document_id": document_id,
                        "status": db_doc.extraction_status,
                        "classification": normalize_classification(db_doc.classification),
                    }
                if db_doc.crew_member_id:
                    from app.models import CrewMember as CrewMemberModel

                    owner = (
                        await session.execute(
                            select(CrewMemberModel)
                            .where(CrewMemberModel.id == db_doc.crew_member_id)
                            .with_for_update()
                        )
                    ).scalar_one_or_none()
                    if owner is None or not is_contractor_profile(owner):
                        db_doc.extraction_status = "rejected"
                        await session.commit()
                        await _cleanup_failed_document_projections(document_id)
                        return {
                            "document_id": document_id,
                            "status": "rejected",
                            "classification": normalize_classification(db_doc.classification),
                        }
                final_crew_member_id = db_doc.crew_member_id
                is_currently_approved_without_evidence = (
                    db_doc.extraction_status == "approved" and not db_doc.extracted_data
                )
                if db_doc.extraction_status == "rejected" or (
                    db_doc.extraction_status == "approved"
                    and not is_currently_approved_without_evidence
                    and not was_approved_without_evidence
                ):
                    terminal_status = db_doc.extraction_status
                    # The row may have been reviewed while extraction was in
                    # flight. Preserve that authoritative terminal decision
                    # in the worker result; leaving final_status unset makes
                    # the task report a false failure and retry successful
                    # review work.
                    final_status = terminal_status
                    final_classification = normalize_classification(db_doc.classification)
                else:
                    db_doc.classification = normalize_classification(doc.classification)
                    final_classification = normalize_classification(db_doc.classification)
                    db_doc.extracted_data = extraction_result
                    db_doc.extracted_text = text if not is_image else None
                    db_doc.extraction_confidence = extraction_service.confidence_from_result(
                        extraction_result
                    )
                    if normalize_classification(db_doc.classification) == "cv":
                        if db_doc.uploaded_by in CV_UPLOADERS_REQUIRING_REJECTION:
                            incoming_review = (
                                await session.execute(
                                    select(IncomingDocumentReview).where(
                                        IncomingDocumentReview.document_id == document_id
                                    )
                                )
                            ).scalar_one_or_none()
                            if incoming_review is not None:
                                incoming_review.status = "rejected"
                                incoming_review.resolved_at = datetime.now(timezone.utc).replace(
                                    tzinfo=None
                                )
                            db_doc.extraction_status = "rejected"
                            terminal_status = "rejected"
                        else:
                            from app.models import CrewMember, CVReview

                            review = (
                                await session.execute(
                                    select(CVReview).where(CVReview.document_id == document_id)
                                )
                            ).scalar_one_or_none()
                            if review is None and db_doc.crew_member_id:
                                crew = await session.get(CrewMember, db_doc.crew_member_id)
                                review = CVReview(
                                    document_id=document_id,
                                    crew_member_id=db_doc.crew_member_id,
                                    submitted_by=db_doc.uploaded_by or "system",
                                    status="awaiting_review",
                                    prior_publication_status=(
                                        crew.publication_status if crew else "draft"
                                    ),
                                    proposed_data=extraction_result,
                                )
                                session.add(review)
                            elif review and review.status not in {"approved", "rejected"}:
                                # A reprocessing run is a new evidence snapshot.
                                # Merging would preserve fields that disappeared
                                # from the current document and let an admin
                                # approve stale data as if it were current.
                                review.proposed_data = extraction_result
                                review.status = "awaiting_review"
                            db_doc.extraction_status = "awaiting_review"
                    else:
                        # An approved row without evidence is a legacy or
                        # incomplete state, not approval for newly extracted
                        # content. Re-enter the reviewable workflow.
                        db_doc.extraction_status = (
                            "needs_review"
                            if (
                                was_approved_without_evidence
                                or is_currently_approved_without_evidence
                                or needs_review
                            )
                            else "extracted"
                        )
                    db_doc.processing_started_at = None
                    final_status = db_doc.extraction_status
                    await session.commit()

            classification = final_classification or normalize_classification(doc.classification)
            if terminal_status is not None:
                from app.services.consultant_knowledge import consultant_knowledge_service

                try:
                    if not await consultant_knowledge_service.reconcile_document_index(document_id):
                        from app.tasks.document_tasks import queue_document_search_reconcile

                        queue_document_search_reconcile(document_id)
                except Exception as exc:
                    logger.warning(
                        "Could not reconcile terminal document projection (%s)",
                        type(exc).__name__,
                    )
                    from app.tasks.document_tasks import queue_document_search_reconcile

                    queue_document_search_reconcile(document_id)
                if terminal_status == "rejected":
                    from app.config import get_settings

                    if get_settings().ENABLE_SEMANTIC_SEARCH:
                        from app.services.qdrant import qdrant_service

                        try:
                            if not await qdrant_service.delete_document(document_id):
                                from app.tasks.document_tasks import (
                                    queue_document_projection_cleanup,
                                )

                                queue_document_projection_cleanup(document_id)
                        except Exception as exc:
                            logger.warning(
                                "Could not remove terminal document vector (%s)",
                                type(exc).__name__,
                            )
                            from app.tasks.document_tasks import queue_document_projection_cleanup

                            queue_document_projection_cleanup(document_id)
                return {
                    "document_id": document_id,
                    "status": terminal_status,
                    "classification": classification,
                }
            if (
                classification == "certificate"
                and final_crew_member_id
                and not needs_review
                and doc.uploaded_by != "contractor-upload-link"
            ):
                from app.services.crew import certification_service

                try:
                    await certification_service.link_extracted_certificate(
                        crew_id=final_crew_member_id,
                        document_id=document_id,
                        extracted_data=extraction_result,
                        confidence=extraction_service.confidence_from_result(extraction_result),
                    )
                except Exception as exc:
                    # The extraction commit above is authoritative. A
                    # certificate projection outage must not send this
                    # successfully extracted document through the failure
                    # handler and erase its searchable state.
                    logger.warning(
                        "Could not link extracted certificate projection (%s)",
                        type(exc).__name__,
                    )
                    from app.tasks.document_tasks import queue_certificate_projection_reconcile

                    queue_certificate_projection_reconcile(document_id)

            from app.services.consultant_knowledge import consultant_knowledge_service

            try:
                if not await consultant_knowledge_service.reconcile_document_index(document_id):
                    from app.tasks.document_tasks import queue_document_search_reconcile

                    queue_document_search_reconcile(document_id)
            except Exception as exc:
                # Extraction is source-of-truth work. A derived search outage
                # must not turn a successfully committed extraction into a
                # misleading failed document.
                logger.warning(
                    "Could not reconcile extracted document projection (%s)",
                    type(exc).__name__,
                )
                from app.tasks.document_tasks import queue_document_search_reconcile

                queue_document_search_reconcile(document_id)

            await _log_extraction_best_effort(
                document_id=document_id,
                model_used=(
                    "deterministic-cv-template"
                    if normalize_classification(doc.classification) == "cv"
                    else "llama3.1:8b"
                ),
                confidence=extraction_service.confidence_from_result(extraction_result),
                status=final_status or "failed",
            )

            return {
                "document_id": document_id,
                "status": final_status or "failed",
                "classification": doc.classification,
                "confidence": extraction_service.confidence_from_result(extraction_result),
            }

        except Exception as e:
            logger.error("Document extraction failed (%s)", type(e).__name__)
            failure_terminal_status: str | None = None
            async with factory() as session:
                stmt = (
                    select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
                )
                result = await session.execute(stmt)
                db_doc = result.scalar_one_or_none()
                if db_doc is None:
                    return {"error": "Document not found", "status": "failed"}
                if db_doc.dropbox_revision != source_revision:
                    return {
                        "document_id": document_id,
                        "status": db_doc.extraction_status,
                        "classification": normalize_classification(db_doc.classification),
                    }
                if db_doc.crew_member_id:
                    from app.models import CrewMember as CrewMemberModel

                    owner = (
                        await session.execute(
                            select(CrewMemberModel)
                            .where(CrewMemberModel.id == db_doc.crew_member_id)
                            .with_for_update()
                        )
                    ).scalar_one_or_none()
                    if owner is None or not is_contractor_profile(owner):
                        db_doc.extraction_status = "rejected"
                        await session.commit()
                        await _cleanup_failed_document_projections(document_id)
                        return {
                            "document_id": document_id,
                            "status": "rejected",
                            "classification": normalize_classification(db_doc.classification),
                        }
                if db_doc.extraction_status in {"approved", "rejected"}:
                    failure_terminal_status = db_doc.extraction_status
                elif db_doc.extraction_status == "processing":
                    if normalize_classification(db_doc.classification) == "cv":
                        from app.models import CVReview

                        review = (
                            await session.execute(
                                select(CVReview)
                                .where(CVReview.document_id == document_id)
                                .with_for_update()
                            )
                        ).scalar_one_or_none()
                        if review is not None and review.status == "processing":
                            review.status = "failed"
                    db_doc.extraction_status = "failed"
                    db_doc.processing_started_at = None
                    await session.commit()
                else:
                    failure_terminal_status = db_doc.extraction_status

            if failure_terminal_status is not None:
                if failure_terminal_status == "rejected":
                    await _cleanup_failed_document_projections(document_id)
                return {
                    "document_id": document_id,
                    "status": failure_terminal_status,
                    "classification": normalize_classification(doc.classification),
                }

            await _cleanup_failed_document_projections(document_id)

            await _log_extraction_best_effort(
                document_id=document_id,
                model_used=(
                    "deterministic-cv-template"
                    if normalize_classification(doc.classification) == "cv"
                    else "llama3.1:8b"
                ),
                confidence={},
                status="failed",
            )

            return {"error": "Document extraction failed", "status": "failed"}

    async def confirm_extraction(
        self,
        document_id: str,
        confirmed_data: dict,
    ) -> Optional[DocumentModel]:
        """Confirm extracted data and save to database.

        Args:
            document_id: UUID of the document.
            confirmed_data: Confirmed extraction data.

        Returns:
            Updated document or None.
        """
        if not isinstance(confirmed_data, dict):
            raise ValueError("Confirmed extraction data must be a JSON object")
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return None
            if doc.crew_member_id:
                from app.models import CrewMember as CrewMemberModel

                crew = (
                    await session.execute(
                        select(CrewMemberModel)
                        .where(CrewMemberModel.id == doc.crew_member_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if crew is None or not is_contractor_profile(crew):
                    raise ValueError("Document is not linked to a contractor profile")
            if doc.extraction_status in {"approved", "rejected"}:
                raise ValueError("Terminal document decisions cannot be overwritten")
            if doc.extraction_status == "processing":
                raise ValueError("Document extraction is currently in progress")
            if normalize_classification(doc.classification) == "cv":
                raise ValueError("CV extraction must be confirmed through the CV review workflow")

            requires_review = doc.uploaded_by == "contractor-upload-link"
            doc.extracted_data = confirmed_data
            doc.extraction_status = "needs_review" if requires_review else "extracted"
            if requires_review:
                incoming_review = (
                    await session.execute(
                        select(IncomingDocumentReview).where(
                            IncomingDocumentReview.document_id == document_id
                        )
                    )
                ).scalar_one_or_none()
                if incoming_review is not None:
                    incoming_review.status = "unread"
                    incoming_review.claimed_by = None
                    incoming_review.claimed_at = None
                    incoming_review.resolved_at = None
            await session.commit()
            await session.refresh(doc)

            if (
                not requires_review
                and normalize_classification(doc.classification) == "certificate"
                and doc.crew_member_id
            ):
                from app.services.crew import certification_service

                try:
                    await certification_service.link_extracted_certificate(
                        crew_id=doc.crew_member_id,
                        document_id=document_id,
                        extracted_data=confirmed_data,
                        confidence=confirmed_data.get("confidence", {}),
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not link confirmed certificate projection (%s)",
                        type(exc).__name__,
                    )
                    from app.tasks.document_tasks import queue_certificate_projection_reconcile

                    queue_certificate_projection_reconcile(document_id)

            await _log_access_best_effort(
                document_id=document_id,
                user_id="system",
                action="confirm_extraction",
                data_keys=list(confirmed_data.keys()),
            )

            from app.services.consultant_knowledge import consultant_knowledge_service

            try:
                if not await consultant_knowledge_service.reconcile_document_index(document_id):
                    from app.tasks.document_tasks import queue_document_search_reconcile

                    queue_document_search_reconcile(document_id)
            except Exception as exc:
                logger.warning(
                    "Could not reconcile confirmed document projection (%s)",
                    type(exc).__name__,
                )
                from app.tasks.document_tasks import queue_document_search_reconcile

                queue_document_search_reconcile(document_id)

            # Manual confirmation is also a transition into a searchable
            # extraction state. Keep the derived semantic projection in sync
            # when that optional feature is enabled.
            from app.tasks.document_tasks import _maybe_queue_embeddings

            if not requires_review:
                _maybe_queue_embeddings(document_id, "extracted")

            return doc

    async def link_to_crew_member(
        self,
        document_id: str,
        crew_id: str,
    ) -> Optional[DocumentModel]:
        """Link a document to a crew member."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return None

            target_crew = (
                await session.execute(
                    select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
                )
            ).scalar_one_or_none()
            if target_crew is None or not is_contractor_profile(target_crew):
                raise ValueError("Crew member not found")

            previous_crew_id = doc.crew_member_id
            if previous_crew_id and previous_crew_id != crew_id:
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
                    crew_id=previous_crew_id,
                    detached_certification_ids=detached_certification_ids,
                    detached_expiry_dates=detached_expiry_dates,
                )

            doc.crew_member_id = crew_id
            await session.commit()
            await session.refresh(doc)

            affected_crew_ids = {crew_id}
            if previous_crew_id:
                affected_crew_ids.add(previous_crew_id)
            for affected_crew_id in affected_crew_ids:
                for cache_key in (
                    cache_service._make_key("compliance", affected_crew_id),
                    cache_service._make_key("summary", affected_crew_id),
                ):
                    try:
                        await cache_service.delete(cache_key)
                    except Exception as exc:
                        logger.warning("Could not clear relink cache (%s)", type(exc).__name__)

            from app.services.consultant_knowledge import consultant_knowledge_service

            try:
                if not await consultant_knowledge_service.reconcile_document_index(document_id):
                    from app.tasks.document_tasks import queue_document_search_reconcile

                    queue_document_search_reconcile(document_id)
            except Exception as exc:
                logger.warning(
                    "Could not reconcile relinked document projection (%s)",
                    type(exc).__name__,
                )
                from app.tasks.document_tasks import queue_document_search_reconcile

                queue_document_search_reconcile(document_id)

            if (
                normalize_classification(doc.classification) == "certificate"
                and doc.extraction_status in {"approved", "extracted"}
                and doc.extracted_data
                and (
                    doc.uploaded_by != "contractor-upload-link"
                    or doc.extraction_status == "approved"
                )
            ):
                from app.services.crew import certification_service

                try:
                    await certification_service.link_extracted_certificate(
                        crew_id=crew_id,
                        document_id=document_id,
                        extracted_data=doc.extracted_data,
                        confidence=(
                            doc.extraction_confidence
                            if isinstance(doc.extraction_confidence, dict)
                            else {}
                        ),
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not link relinked certificate projection (%s)",
                        type(exc).__name__,
                    )
                    from app.tasks.document_tasks import queue_certificate_projection_reconcile

                    queue_certificate_projection_reconcile(document_id)
            from app.config import get_settings

            if get_settings().ENABLE_SEMANTIC_SEARCH:
                from app.services.qdrant import qdrant_service

                should_reindex = doc.extraction_status in {"approved", "extracted"} and (
                    doc.uploaded_by != "contractor-upload-link"
                    or doc.extraction_status == "approved"
                )
                if should_reindex:
                    try:
                        deleted = await qdrant_service.delete_document(document_id)
                    except Exception as exc:
                        logger.warning(
                            "Could not remove relinked document vector (%s)", type(exc).__name__
                        )
                        deleted = False
                    # A searchable document needs an upsert after relinking,
                    # whether deletion succeeded or needs retry. Do not use
                    # the cleanup task here because it would remove a valid
                    # vector after a successful retry.
                    try:
                        from app.tasks.document_tasks import index_document_embeddings

                        index_document_embeddings.delay(document_id)
                    except Exception as exc:
                        logger.warning(
                            "Could not queue semantic reindex after document relink (%s)",
                            type(exc).__name__,
                        )
                        from app.tasks.document_tasks import queue_document_projection_cleanup

                        # The old vector was already removed. Let the cleanup
                        # worker recheck source visibility and retry the
                        # current embedding instead of acknowledging a
                        # permanently missing semantic projection.
                        queue_document_projection_cleanup(document_id)
                else:
                    try:
                        deleted = await qdrant_service.delete_document(document_id)
                    except Exception as exc:
                        logger.warning(
                            "Could not remove unpublished relinked document vector (%s)",
                            type(exc).__name__,
                        )
                        deleted = False
                    if not deleted:
                        from app.tasks.document_tasks import queue_document_projection_cleanup

                        queue_document_projection_cleanup(document_id)
            return doc


document_service = DocumentService()
