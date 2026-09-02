from __future__ import annotations

import logging

from sqlalchemy import and_, select

from app.services.sync_processor import sync_processor
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=10)
def process_document_extraction(self, document_id: str) -> dict:
    """Process document extraction via LLM (synchronous for Celery).

    Args:
        document_id: UUID of the document to process.

    Returns:
        Dict with extraction results.
    """
    try:
        logger.info(f"Processing document extraction: {document_id}")
        result = sync_processor.process(document_id)
        return result
    except Exception as exc:
        logger.error(f"Extraction failed for {document_id}: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=10)
def process_dropbox_document(self, document_id: str) -> dict:
    """Process a document from Dropbox.

    Args:
        document_id: UUID of the document to process.

    Returns:
        Dict with processing results.
    """
    try:
        logger.info(f"Processing Dropbox document: {document_id}")
        result = sync_processor.process(document_id)
        return result
    except Exception as exc:
        logger.error(f"Dropbox processing failed for {document_id}: {exc}")
        raise self.retry(exc=exc)


@celery_app.task
def check_expiring_certifications() -> dict:
    """Check for certifications expiring soon and notify staff."""
    logger.info("Checking expiring certifications")
    try:
        from datetime import date, timedelta

        from app.models import Certification
        from app.services.sync_processor import get_sync_session

        session = get_sync_session()
        try:
            today = date.today()
            threshold = today + timedelta(days=30)

            stmt = select(Certification).where(
                and_(
                    Certification.expiry_date < threshold,
                    Certification.status == "valid",
                )
            )
            result = session.execute(stmt)
            certs = result.scalars().all()

            updated = 0
            for cert in certs:
                if cert.expiry_date < today:
                    cert.status = "expired"
                else:
                    cert.status = "expiring_soon"
                updated += 1

            session.commit()
            return {"status": "completed", "updated": updated}
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Certification check failed: {e}")
        return {"status": "failed", "error": str(e)}


@celery_app.task
def index_document_embeddings(document_id: str) -> dict:
    """Index document embeddings in Qdrant.

    Args:
        document_id: UUID of the document to index.
    """
    logger.info(f"Indexing embeddings for document: {document_id}")
    try:
        from app.services.sync_processor import get_sync_session

        session = get_sync_session()
        try:
            from app.models import Document as DocumentModel

            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = session.execute(stmt)
            doc = result.scalar_one_or_none()
            if not doc:
                return {"document_id": document_id, "status": "failed", "error": "not found"}

            # Determine indexable text: prefer extracted_data, fallback to file_name/classification
            import json as _json

            indexable_text = None
            if doc.extracted_data:
                indexable_text = _json.dumps(doc.extracted_data, default=str)
            elif doc.classification:
                indexable_text = f"{doc.classification} document {doc.file_name}"
            else:
                indexable_text = doc.file_name

            import asyncio

            from app.services.qdrant import qdrant_service

            ok = asyncio.run(
                qdrant_service.index_document(
                    doc.id,
                    indexable_text,
                    metadata={
                        "file_name": doc.file_name,
                        "classification": doc.classification,
                        "crew_member_id": doc.crew_member_id,
                        "extraction_status": doc.extraction_status,
                    },
                )
            )
            return {
                "document_id": document_id,
                "status": "indexed" if ok else "failed",
            }
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to index embeddings for {document_id}: {e}")
        return {"document_id": document_id, "status": "failed", "error": str(e)}
