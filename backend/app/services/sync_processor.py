from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.domain.document_processing import processing_claim_is_stale
from app.domain.fields import CV_UPLOADERS_REQUIRING_REJECTION, normalize_classification
from app.models import CVReview
from app.services.extraction import extraction_service

settings = get_settings()
logger = logging.getLogger(__name__)
_processing_claim_is_stale = processing_claim_is_stale

sync_engine: Engine | None = None
SyncSessionFactory: sessionmaker[Session] | None = None


def _final_extraction_status(
    classification: str,
    extracted_status: str,
    *,
    approved_without_evidence: bool,
) -> str:
    """Keep reprocessed evidence behind the correct publication gate."""
    if classification == "cv":
        return extracted_status
    if approved_without_evidence:
        return "needs_review"
    return extracted_status


def _reset_cv_review_decision(review: CVReview) -> None:
    """Clear a prior decision when Dropbox supplies a new CV snapshot."""
    review.status = "awaiting_review"
    review.approved_data = None
    review.reviewed_by = None
    review.review_note = None
    review.reviewed_at = None


def _delete_semantic_projection(document_id: str) -> None:
    """Remove stale Qdrant state without starting an event loop in Celery."""
    if not settings.ENABLE_SEMANTIC_SEARCH:
        return
    from app.services.qdrant import qdrant_service

    try:
        deleted = qdrant_service.delete_document_sync(document_id)
    except Exception as exc:
        logger.warning("Semantic projection cleanup failed (%s)", type(exc).__name__)
        deleted = False
    if not deleted:
        logger.warning("Semantic projection cleanup was not confirmed")
        from app.tasks.document_tasks import queue_document_projection_cleanup

        queue_document_projection_cleanup(document_id)


def _log_extraction_sync(
    document_id: str,
    *,
    model_used: str,
    confidence: dict[str, Any],
    status: str,
) -> None:
    """Record worker extraction history without changing extraction outcome."""
    import asyncio

    from app.database import dispose_engine
    from app.services.audit import audit_service

    async def _log_and_release_engine() -> None:
        try:
            await audit_service.log_extraction(
                document_id=document_id,
                model_used=model_used,
                confidence=confidence,
                status=status,
            )
        finally:
            # The audit call uses the async engine from a throwaway loop.
            await dispose_engine()

    try:
        asyncio.run(_log_and_release_engine())
    except Exception as exc:
        # Extraction has already been committed. Audit availability must not
        # make a successful worker run retry and duplicate the extraction.
        logger.warning("Could not record extraction audit (%s)", type(exc).__name__)


def get_sync_engine() -> Engine:
    global sync_engine, SyncSessionFactory
    if sync_engine is None:
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql+asyncpg"):
            # Prefer psycopg2 driver (installed via psycopg2-binary); fallback to plain postgresql
            candidate = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
            try:
                # Test import of driver - quick check before create_engine
                import psycopg2  # noqa: F401

                db_url = candidate
            except ImportError:
                db_url = db_url.replace("postgresql+asyncpg", "postgresql")
                logger.warning(
                    "psycopg2 not installed, using default postgresql driver for sync engine"
                )
        elif db_url.startswith("sqlite+aiosqlite"):
            db_url = db_url.replace("sqlite+aiosqlite", "sqlite")
        try:
            sync_engine = create_engine(db_url, pool_pre_ping=True)
        except Exception as e:
            # If psycopg2 variant failed, try plain
            if "+psycopg2" in db_url:
                fallback = db_url.replace("postgresql+psycopg2", "postgresql")
                logger.warning(
                    "Sync engine with psycopg2 failed (%s), retrying with fallback driver",
                    type(e).__name__,
                )
                sync_engine = create_engine(fallback, pool_pre_ping=True)
            else:
                raise
        SyncSessionFactory = sessionmaker(bind=sync_engine, expire_on_commit=False)
    return sync_engine


def get_sync_session() -> Session:
    get_sync_engine()
    if SyncSessionFactory is None:
        raise RuntimeError("get_sync_session: session factory was not initialized")
    return SyncSessionFactory()


class SyncDocumentProcessor:
    """Synchronous document processor for Celery tasks."""

    def process(self, document_id: str) -> dict:
        """Process a document through the extraction pipeline."""
        session = get_sync_session()
        try:
            from app.models import Document as DocumentModel

            stmt = select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
            result = session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return {"error": "Document not found", "status": "failed"}
            if getattr(doc, "crew_member_id", None):
                from app.domain.crew_accounts import is_contractor_profile
                from app.models import CrewMember

                crew = session.execute(
                    select(CrewMember)
                    .where(CrewMember.id == doc.crew_member_id)
                    .with_for_update()
                ).scalar_one_or_none()
                if crew is None or not is_contractor_profile(crew):
                    doc.extraction_status = "rejected"
                    session.commit()
                    _delete_semantic_projection(document_id)
                    return {
                        "document_id": document_id,
                        "status": "rejected",
                        "classification": normalize_classification(doc.classification),
                    }
            approved_without_evidence = (
                doc.extraction_status == "approved" and not doc.extracted_data
            )
            if doc.extraction_status == "processing":
                if not processing_claim_is_stale(doc.processing_started_at):
                    return {
                        "document_id": document_id,
                        "status": "processing",
                        "classification": normalize_classification(doc.classification),
                    }
                logger.warning("Recovering stale document extraction claim")
                doc.extraction_status = "pending"
            if doc.extraction_status == "rejected" or (
                doc.extraction_status == "approved" and not approved_without_evidence
            ):
                if doc.extraction_status == "rejected":
                    _delete_semantic_projection(document_id)
                return {
                    "document_id": document_id,
                    "status": doc.extraction_status,
                    "classification": normalize_classification(doc.classification),
                }
            if doc.extraction_status not in {"pending", "failed"} and not approved_without_evidence:
                return {
                    "document_id": document_id,
                    "status": doc.extraction_status,
                    "classification": normalize_classification(doc.classification),
                }
            source_revision = doc.dropbox_revision

            if normalize_classification(doc.classification) == "cv":
                from app.models import CVReview

                existing_review = session.execute(
                    select(CVReview).where(CVReview.document_id == document_id)
                ).scalar_one_or_none()
                if existing_review and existing_review.status in {"approved", "rejected"}:
                    if existing_review.status == "rejected":
                        _delete_semantic_projection(document_id)
                    return {
                        "document_id": document_id,
                        "status": existing_review.status,
                        "classification": "cv",
                    }

            doc.extraction_status = "processing"
            doc.processing_started_at = datetime.now(timezone.utc)
            session.commit()

            try:
                from app.services.text_extraction import text_extraction_service
                from app.services.upload import document_upload_service

                # ``storage_path`` is a Dropbox identifier when Dropbox is the
                # source of record.  PDF/DOC readers need a filesystem path,
                # so resolve the managed local cache (downloading into it when
                # necessary) before passing the document to the extractor.
                file_content = document_upload_service.get_file(doc.storage_path)
                if file_content is None:
                    raise FileNotFoundError("Managed document file is unavailable")
                valid, validation_error = document_upload_service.validate_file_content(
                    doc.file_name, file_content
                )
                if not valid:
                    raise ValueError(f"Stored document failed validation: {validation_error}")
                local_path = document_upload_service._get_local_cache_path(doc.storage_path)
                if not local_path or not local_path.exists():
                    raise FileNotFoundError("Managed document cache is unavailable")
                extraction_path = str(local_path)

                is_image = text_extraction_service.is_image(doc.file_type)

                if is_image:
                    doc.classification = normalize_classification(
                        doc.classification or "certificate"
                    )
                    extraction_result = extraction_service.extract_from_image_sync(
                        extraction_path,
                        doc.classification,
                    )
                else:
                    text = text_extraction_service.extract_text_sync(extraction_path, doc.file_type)

                    if not doc.classification:
                        classification_result = extraction_service.classify_document_sync(text)
                        doc.classification = extraction_service.classification_from_result(
                            classification_result
                        )

                    classification: str = normalize_classification(doc.classification)
                    if doc.classification != classification:
                        doc.classification = classification

                    from app.services.cv_processing import CVProcessingService

                    if classification == "cv":
                        # CVs never go through the LLM — see
                        # CVProcessingService.extract_cv_deterministically
                        # and backend/docs/consultant-knowledge-core.md.
                        extraction_result = CVProcessingService.extract_cv_deterministically(
                            extraction_path, doc.file_type, text
                        )
                    else:
                        extraction_result = extraction_service.extract_document_sync(
                            text, classification
                        )

                status, _ = extraction_service.determine_review_status(extraction_result)

                with session.no_autoflush:
                    latest_doc = session.execute(
                        select(DocumentModel)
                        .where(DocumentModel.id == document_id)
                        .execution_options(populate_existing=True)
                        .with_for_update()
                    ).scalar_one_or_none()
                if latest_doc is None:
                    return {"error": "Document not found", "status": "failed"}
                if latest_doc.dropbox_revision != source_revision:
                    return {
                        "document_id": document_id,
                        "status": latest_doc.extraction_status,
                        "classification": normalize_classification(latest_doc.classification),
                    }
                if latest_doc.crew_member_id:
                    from app.domain.crew_accounts import is_contractor_profile
                    from app.models import CrewMember

                    owner = session.execute(
                        select(CrewMember)
                        .where(CrewMember.id == latest_doc.crew_member_id)
                        .with_for_update()
                    ).scalar_one_or_none()
                    if owner is None or not is_contractor_profile(owner):
                        latest_doc.extraction_status = "rejected"
                        session.commit()
                        _delete_semantic_projection(document_id)
                        return {
                            "document_id": document_id,
                            "status": "rejected",
                            "classification": normalize_classification(latest_doc.classification),
                        }
                approved_without_evidence = (
                    latest_doc.extraction_status == "approved" and not latest_doc.extracted_data
                )
                if latest_doc.extraction_status == "rejected" or (
                    latest_doc.extraction_status == "approved" and not approved_without_evidence
                ):
                    if latest_doc.extraction_status == "rejected":
                        _delete_semantic_projection(document_id)
                    return {
                        "document_id": document_id,
                        "status": latest_doc.extraction_status,
                        "classification": normalize_classification(latest_doc.classification),
                    }
                doc = latest_doc

                doc.extracted_data = extraction_result
                doc.extracted_text = text if not is_image else None
                raw_confidence = extraction_result.get("confidence")
                doc.extraction_confidence = (
                    raw_confidence if isinstance(raw_confidence, dict) else {}
                )

                classification = normalize_classification(doc.classification)
                should_link_certificate = False

                # CV data is staged for an administrator. It must not update
                # the canonical/searchable profile before explicit approval.
                if classification == "cv" and doc.crew_member_id:
                    from app.models import CVReview

                    if doc.uploaded_by in CV_UPLOADERS_REQUIRING_REJECTION:
                        from app.models import IncomingDocumentReview

                        doc.extraction_status = "rejected"
                        incoming_review = session.execute(
                            select(IncomingDocumentReview).where(
                                IncomingDocumentReview.document_id == document_id
                            )
                        ).scalar_one_or_none()
                        if incoming_review is not None:
                            incoming_review.status = "rejected"
                            incoming_review.resolved_at = datetime.now(timezone.utc).replace(
                                tzinfo=None
                            )
                        session.commit()
                        _delete_semantic_projection(document_id)
                        return {
                            "document_id": document_id,
                            "status": "rejected",
                            "classification": classification,
                        }

                    review = session.execute(
                        select(CVReview).where(CVReview.document_id == document_id)
                    ).scalar_one_or_none()
                    if review is None:
                        from app.models import CrewMember

                        crew = session.get(CrewMember, doc.crew_member_id)
                        review = CVReview(
                            document_id=document_id,
                            crew_member_id=doc.crew_member_id,
                            submitted_by=doc.uploaded_by or "system",
                            status="awaiting_review" if status != "failed" else "failed",
                            prior_publication_status=(crew.publication_status if crew else "draft"),
                            proposed_data=extraction_result,
                        )
                        session.add(review)
                    else:
                        # Reprocessing replaces the evidence snapshot. Do not
                        # carry fields forward from an older CV extraction.
                        review.proposed_data = extraction_result
                        _reset_cv_review_decision(review)
                        if status != "failed":
                            review.status = "awaiting_review"
                        else:
                            review.status = "failed"
                    status = "awaiting_review" if status != "failed" else "failed"

                elif (
                    classification == "certificate"
                    and doc.crew_member_id
                    and status == "extracted"
                    # Contractor-link uploads are review-gated. Their
                    # extracted evidence must not become a live certification
                    # projection until a staff member approves the review.
                    and doc.uploaded_by != "contractor-upload-link"
                ):
                    should_link_certificate = True

                doc.extraction_status = _final_extraction_status(
                    classification,
                    status,
                    approved_without_evidence=approved_without_evidence,
                )
                session.commit()
                if should_link_certificate:
                    import asyncio

                    from app.database import dispose_engine
                    from app.services.crew import certification_service

                    crew_member_id = doc.crew_member_id
                    if crew_member_id is None:
                        raise RuntimeError("Certificate document has no crew member")
                    linked_crew_member_id: str = crew_member_id
                    linked_document = doc
                    if linked_document is None:
                        raise RuntimeError("Certificate document disappeared before linking")
                    link_confidence = linked_document.extraction_confidence

                    # Sync Celery-worker context only: asyncio.run() cannot
                    # nest inside a running loop — fail loudly instead of a
                    # cryptic RuntimeError deep in the call stack.
                    try:
                        asyncio.get_running_loop()
                    except RuntimeError:
                        pass
                    else:
                        raise RuntimeError(
                            "SyncDocumentProcessor.process must be called from a "
                            "sync context (Celery worker), not a running event loop"
                        )

                    async def _link_cert_and_release_engine() -> None:
                        try:
                            await certification_service.link_extracted_certificate(
                                crew_id=linked_crew_member_id,
                                document_id=document_id,
                                extracted_data=extraction_result,
                                confidence=link_confidence,
                            )
                        finally:
                            # Intentional worker hygiene, not collateral damage:
                            # asyncpg connections bind to the asyncio.run()
                            # throwaway loop, so the singleton must be dropped
                            # before the next document in this worker process.
                            await dispose_engine()

                    try:
                        asyncio.run(_link_cert_and_release_engine())
                    except Exception as exc:
                        # Extraction was committed before this derived
                        # certification projection opened its own transaction.
                        # Do not rewrite a successful extraction as failed;
                        # queue a bounded repair instead.
                        logger.warning(
                            "Could not link extracted certificate projection (%s)",
                            type(exc).__name__,
                        )
                        from app.tasks.document_tasks import queue_certificate_projection_reconcile

                        queue_certificate_projection_reconcile(document_id)
                _log_extraction_sync(
                    document_id,
                    model_used="deterministic-cv-template"
                    if classification == "cv"
                    else "llama3.1:8b",
                    confidence=doc.extraction_confidence or {},
                    status=doc.extraction_status,
                )
                return {
                    "document_id": document_id,
                    "status": doc.extraction_status,
                    "classification": doc.classification,
                }

            except Exception as e:
                # Exception messages may contain a CV filename or storage path.
                # Keep the failure observable without logging private metadata.
                logger.error("Document extraction failed (%s)", type(e).__name__)
                # The exception may have come from session.commit(). Reset the
                # failed transaction before attempting to read and mark the
                # authoritative row; otherwise SQLAlchemy raises
                # PendingRollbackError and leaves the document in processing.
                session.rollback()
                latest_doc = session.execute(
                    select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
                ).scalar_one_or_none()
                if latest_doc is None:
                    return {"error": "Document not found", "status": "failed"}
                if latest_doc.dropbox_revision != source_revision:
                    return {
                        "document_id": document_id,
                        "status": latest_doc.extraction_status,
                        "classification": normalize_classification(latest_doc.classification),
                    }
                if latest_doc.extraction_status in {"approved", "rejected"}:
                    if latest_doc.extraction_status == "rejected":
                        _delete_semantic_projection(document_id)
                    return {
                        "document_id": document_id,
                        "status": latest_doc.extraction_status,
                        "classification": normalize_classification(latest_doc.classification),
                    }
                if latest_doc.extraction_status != "processing":
                    return {
                        "document_id": document_id,
                        "status": latest_doc.extraction_status,
                        "classification": normalize_classification(latest_doc.classification),
                    }
                if normalize_classification(latest_doc.classification) == "cv":
                    from app.models import CVReview

                    review = session.execute(
                        select(CVReview).where(CVReview.document_id == document_id).with_for_update()
                    ).scalar_one_or_none()
                    if review is not None and review.status == "processing":
                        review.status = "failed"
                latest_doc.extraction_status = "failed"
                latest_doc.processing_started_at = None
                session.commit()
                _delete_semantic_projection(document_id)
                _log_extraction_sync(
                    document_id,
                    model_used="deterministic-cv-template"
                    if normalize_classification(latest_doc.classification) == "cv"
                    else "llama3.1:8b",
                    confidence={},
                    status="failed",
                )
                return {"error": "Document extraction failed", "status": "failed"}

        finally:
            session.close()


sync_processor = SyncDocumentProcessor()
