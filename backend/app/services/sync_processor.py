from __future__ import annotations

import logging

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.domain.fields import normalize_classification
from app.services.extraction import extraction_service

settings = get_settings()
logger = logging.getLogger(__name__)

sync_engine: Engine | None = None
SyncSessionFactory: sessionmaker[Session] | None = None


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
                logger.warning(f"Sync engine with psycopg2 failed ({e}), retrying with {fallback}")
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

            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return {"error": "Document not found", "status": "failed"}

            if doc.classification == "cv":
                from app.models import CVReview

                existing_review = session.execute(
                    select(CVReview).where(CVReview.document_id == document_id)
                ).scalar_one_or_none()
                if existing_review and existing_review.status in {"approved", "rejected"}:
                    return {
                        "document_id": document_id,
                        "status": existing_review.status,
                        "classification": "cv",
                    }

            doc.extraction_status = "processing"
            session.commit()

            try:
                from app.services.text_extraction import text_extraction_service
                from app.services.upload import document_upload_service

                # ``storage_path`` is a Dropbox identifier when Dropbox is the
                # source of record.  PDF/DOC readers need a filesystem path,
                # so resolve the managed local cache (downloading into it when
                # necessary) before passing the document to the extractor.
                if document_upload_service.get_file(doc.storage_path) is None:
                    raise FileNotFoundError("Managed document file is unavailable")
                local_path = document_upload_service._get_local_cache_path(doc.storage_path)
                if not local_path or not local_path.exists():
                    raise FileNotFoundError("Managed document cache is unavailable")
                extraction_path = str(local_path)

                is_image = text_extraction_service.is_image(doc.file_type)

                if is_image:
                    extraction_result = extraction_service.extract_from_image_sync(
                        extraction_path,
                        normalize_classification(doc.classification or "certificate"),
                    )
                else:
                    text = text_extraction_service.extract_text_sync(extraction_path, doc.file_type)

                    if not doc.classification:
                        classification_result = extraction_service.classify_document_sync(text)
                        doc.classification = classification_result.get("classification", "other")
                        session.commit()

                    classification: str = normalize_classification(doc.classification)
                    if doc.classification != classification:
                        doc.classification = classification
                        session.commit()

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

                doc.extracted_data = extraction_result
                doc.extracted_text = text if not is_image else None
                raw_confidence = extraction_result.get("confidence")
                doc.extraction_confidence = (
                    raw_confidence if isinstance(raw_confidence, dict) else {}
                )

                classification = normalize_classification(doc.classification)

                # CV data is staged for an administrator. It must not update
                # the canonical/searchable profile before explicit approval.
                if classification == "cv" and doc.crew_member_id:
                    from app.models import CVReview

                    review = session.execute(
                        select(CVReview).where(CVReview.document_id == document_id)
                    ).scalar_one_or_none()
                    if review is not None:
                        review.proposed_data = {**(review.proposed_data or {}), **extraction_result}
                        review.status = "awaiting_review" if status != "failed" else "failed"
                    status = "awaiting_review" if status != "failed" else "failed"

                elif classification == "certificate" and doc.crew_member_id:
                    import asyncio

                    from app.database import dispose_engine
                    from app.services.crew import certification_service

                    crew_member_id = doc.crew_member_id

                    async def _link_cert_and_release_engine() -> None:
                        try:
                            await certification_service.link_extracted_certificate(
                                crew_id=crew_member_id,
                                document_id=document_id,
                                extracted_data=extraction_result,
                                confidence=doc.extraction_confidence,
                            )
                        finally:
                            await dispose_engine()

                    asyncio.run(_link_cert_and_release_engine())

                doc.extraction_status = status
                session.commit()
                return {
                    "document_id": document_id,
                    "status": doc.extraction_status,
                    "classification": doc.classification,
                }

            except Exception as e:
                # Exception messages may contain a CV filename or storage path.
                # Keep the failure observable without logging private metadata.
                logger.error("Document extraction failed (%s)", type(e).__name__)
                doc.extraction_status = "failed"
                session.commit()
                return {"error": str(e), "status": "failed"}

        finally:
            session.close()


sync_processor = SyncDocumentProcessor()
