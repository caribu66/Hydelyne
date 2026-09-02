from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.services.extraction import extraction_service

settings = get_settings()
logger = logging.getLogger(__name__)

sync_engine = None
SyncSessionFactory = None


def get_sync_engine():
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
                        extraction_path, doc.classification or "certificate"
                    )
                else:
                    text = text_extraction_service.extract_text_sync(extraction_path, doc.file_type)

                    if not doc.classification:
                        classification_result = extraction_service.classify_document_sync(text)
                        doc.classification = classification_result.get("classification", "other")
                        session.commit()

                    from app.services.cv_processing import CVProcessingService

                    if doc.classification == "cv":
                        # CVs never go through the LLM — see
                        # CVProcessingService.extract_cv_deterministically
                        # and backend/docs/consultant-knowledge-core.md.
                        extraction_result = CVProcessingService.extract_cv_deterministically(
                            extraction_path, doc.file_type, text
                        )
                    else:
                        extraction_result = extraction_service.extract_document_sync(
                            text, doc.classification
                        )

                status, _ = extraction_service.determine_review_status(extraction_result)

                doc.extracted_data = extraction_result
                doc.extracted_text = text if not is_image else None
                raw_confidence = extraction_result.get("confidence")
                doc.extraction_confidence = (
                    raw_confidence if isinstance(raw_confidence, dict) else {}
                )

                # If this is a CV, process the extracted data into crew member profile
                if doc.classification == "cv" and doc.crew_member_id:
                    import asyncio

                    from app.database import dispose_engine
                    from app.services.cv_processing import cv_processing_service

                    async def _enrich_profile_and_release_engine() -> None:
                        # This processor is called by synchronous Celery tasks;
                        # run the async profile-enrichment service to completion,
                        # then dispose the async engine before this event loop
                        # closes. asyncio.run() opens a fresh loop every call, so
                        # a long-lived worker process reusing the async engine
                        # singleton across tasks fails on the second CV with
                        # "attached to a different loop" — disposing releases the
                        # singleton so the next task's asyncio.run() call gets a
                        # fresh engine bound to its own fresh loop.
                        try:
                            await cv_processing_service.process_cv_extraction(
                                crew_member_id=doc.crew_member_id,
                                extracted_data=extraction_result,
                                document_id=document_id,
                            )
                        finally:
                            await dispose_engine()

                    asyncio.run(_enrich_profile_and_release_engine())

                # Do not expose a terminal document status until any CV fields
                # have been committed.  The UI uses this state to refresh the
                # crew profile after an upload.
                doc.extraction_status = status
                session.commit()
                return {
                    "document_id": document_id,
                    "status": doc.extraction_status,
                    "classification": doc.classification,
                }

            except Exception as e:
                # exception(), not error(): without the traceback an extraction
                # failure only reports the exception text, which is rarely enough
                # to locate the stage that broke.
                logger.exception(f"Extraction failed for {document_id}: {e}")
                doc.extraction_status = "failed"
                session.commit()
                return {"error": str(e), "status": "failed"}

        finally:
            session.close()


sync_processor = SyncDocumentProcessor()
