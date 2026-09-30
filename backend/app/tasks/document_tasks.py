from __future__ import annotations

import logging
from typing import Any, Optional

from celery import Task
from sqlalchemy import select

from app.config import get_settings
from app.services.sync_processor import sync_processor
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


SEARCHABLE_EXTRACTION_STATUSES = {"approved", "extracted"}
ProjectionInput = tuple[str, dict[str, Optional[str]], Optional[str]]


def _load_document_projection_input(
    session: Any,
    document_id: str,
) -> tuple[Optional[ProjectionInput], str]:
    """Read a fresh, currently publishable document projection input.

    Projection work can outlive the transaction that queued it. Always copy
    the source values before releasing the read transaction so a later status
    or revision change can be detected after the external Qdrant write.
    """
    from app.domain.crew_accounts import is_contractor_profile
    from app.models import CrewMember
    from app.models import Document as DocumentModel
    from app.services.qdrant import document_indexable_text

    session.expire_all()
    result = session.execute(
        select(DocumentModel)
        .where(DocumentModel.id == document_id)
        .execution_options(populate_existing=True)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        session.rollback()
        return None, "not found"
    if doc.extraction_status not in SEARCHABLE_EXTRACTION_STATUSES:
        session.rollback()
        return None, "document is not searchable"
    if doc.uploaded_by == "contractor-upload-link" and doc.extraction_status != "approved":
        session.rollback()
        return None, "contractor document is awaiting approval"
    if not doc.crew_member_id:
        session.rollback()
        return None, "document has no published contractor"
    crew = session.get(CrewMember, doc.crew_member_id)
    if crew is None or not is_contractor_profile(crew) or crew.publication_status != "approved":
        session.rollback()
        return None, "contractor is not published"

    projection_input = (
        document_indexable_text(doc),
        {
            "file_name": doc.file_name,
            "classification": doc.classification,
            "crew_member_id": doc.crew_member_id,
            "extraction_status": doc.extraction_status,
        },
        doc.dropbox_revision,
    )
    session.rollback()
    return projection_input, ""


async def _is_searchable_document(document_id: str) -> bool:
    """Check whether a document currently has a valid semantic projection scope."""
    from app.database import get_session_factory
    from app.models import CrewMember
    from app.models import Document as DocumentModel

    async with get_session_factory()() as session:
        document = await session.get(DocumentModel, document_id)
        if document is None or document.extraction_status not in SEARCHABLE_EXTRACTION_STATUSES:
            return False
        if (
            document.uploaded_by == "contractor-upload-link"
            and document.extraction_status != "approved"
        ):
            return False
        if not document.crew_member_id:
            return False
        crew = await session.get(CrewMember, document.crew_member_id)
        return (
            crew is not None
            and crew.password_hash is None
            and crew.role not in {"staff", "admin"}
            and crew.publication_status == "approved"
        )


def _raise_for_retryable_failure(result: dict[str, Any]) -> None:
    """Make swallowed processor failures visible to Celery retry handling."""
    if result.get("status") == "failed" and result.get("error") != "Document not found":
        raise RuntimeError("document extraction failed")


def _maybe_queue_embeddings(document_id: str, extraction_status: str) -> None:
    """Dispatch semantic-search indexing, gated behind ENABLE_SEMANTIC_SEARCH.

    Off by default: Qdrant indexing is validated but not yet earned a
    default-on switch. See backend/docs/consultant-knowledge-core.md (Phase 3).
    """
    if (
        not get_settings().ENABLE_SEMANTIC_SEARCH
        or extraction_status not in SEARCHABLE_EXTRACTION_STATUSES
    ):
        return
    try:
        index_document_embeddings.delay(document_id)
    except Exception as exc:
        # Semantic indexing is additive; never let a broker hiccup here fail
        # extraction, which already succeeded by this point.
        logger.warning("Could not queue embedding indexing (%s)", type(exc).__name__)


def _queue_embedding_reconcile(document_id: str) -> bool:
    """Best-effort requeue after an indexing worker detects a newer source."""
    try:
        index_document_embeddings.delay(document_id)
        return True
    except Exception as exc:
        logger.warning("Could not requeue changed document embedding (%s)", type(exc).__name__)
        return False


def _reconcile_document_search(document_id: str) -> None:
    """Update the keyword-search projection after synchronous extraction."""
    import asyncio

    from app.database import dispose_engine
    from app.services.consultant_knowledge import consultant_knowledge_service

    async def _run() -> None:
        try:
            if not await consultant_knowledge_service.reconcile_document_index(document_id):
                queue_document_search_reconcile(document_id)
        finally:
            await dispose_engine()

    try:
        asyncio.run(_run())
    except Exception as exc:
        # Search is derived state; extraction remains successful and the next
        # retry can repair a provider outage. Queue it here as well as for a
        # false result: provider adapters may fail by raising instead of
        # returning a negative acknowledgement.
        logger.warning("Could not reconcile document search projection (%s)", type(exc).__name__)
        queue_document_search_reconcile(document_id)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def cleanup_document_projections(self: Task, document_id: str) -> dict[str, str]:
    """Retry removal of derived projections after a committed deletion."""
    import asyncio

    from app.database import dispose_engine
    from app.services.consultant_knowledge import consultant_knowledge_service

    async def _run() -> None:
        try:
            if not await consultant_knowledge_service.reconcile_document_index(document_id):
                raise RuntimeError("document search cleanup was not confirmed")
            if get_settings().ENABLE_SEMANTIC_SEARCH:
                from app.services.qdrant import qdrant_service

                if not await qdrant_service.delete_document(document_id):
                    raise RuntimeError("document embedding cleanup was not confirmed")
                if await _is_searchable_document(document_id) and not _queue_embedding_reconcile(
                    document_id
                ):
                    raise RuntimeError("current document embedding requeue was not confirmed")
        finally:
            await dispose_engine()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.warning("Document projection cleanup failed (%s)", type(exc).__name__)
        raise self.retry(exc=exc) from exc
    return {"document_id": document_id, "status": "cleaned"}


def queue_document_projection_cleanup(document_id: str) -> None:
    """Best-effort dispatch for cleanup that outlives a deleted source row."""
    try:
        cleanup_document_projections.delay(document_id)
    except Exception as exc:
        logger.warning("Could not queue document projection cleanup (%s)", type(exc).__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def reconcile_document_search_projection(self: Task, document_id: str) -> dict[str, str]:
    """Retry Meilisearch reconciliation without changing semantic vectors."""
    import asyncio

    from app.database import dispose_engine
    from app.services.consultant_knowledge import consultant_knowledge_service

    async def _run() -> None:
        try:
            if not await consultant_knowledge_service.reconcile_document_index(document_id):
                raise RuntimeError("document search reconciliation was not confirmed")
        finally:
            await dispose_engine()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.warning("Document search reconciliation failed (%s)", type(exc).__name__)
        raise self.retry(exc=exc) from exc
    return {"document_id": document_id, "status": "reconciled"}


def queue_document_search_reconcile(document_id: str) -> None:
    """Best-effort dispatch for a failed Meilisearch reconciliation."""
    try:
        reconcile_document_search_projection.delay(document_id)
    except Exception as exc:
        logger.warning("Could not queue document search reconciliation (%s)", type(exc).__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def reconcile_certificate_projection(self: Task, document_id: str) -> dict[str, str]:
    """Retry certificate linking after the document source row commits."""
    import asyncio

    from app.database import dispose_engine, get_session_factory
    from app.domain.fields import normalize_classification
    from app.models import Document
    from app.services.crew import certification_service

    async def _run() -> None:
        try:
            crew_id: str | None = None
            extracted_data: dict[str, Any] | None = None
            confidence: dict[str, Any] = {}
            async with get_session_factory()() as session:
                document = await session.get(Document, document_id)
                if (
                    document is None
                    or normalize_classification(document.classification) != "certificate"
                    or not document.crew_member_id
                    or document.extraction_status not in {"extracted", "approved"}
                    or not isinstance(document.extracted_data, dict)
                ):
                    return
                crew_id = document.crew_member_id
                extracted_data = dict(document.extracted_data)
                confidence = (
                    dict(document.extraction_confidence)
                    if isinstance(document.extraction_confidence, dict)
                    else {}
                )
            # The linker owns its own transaction. Close the read session
            # first so a long-running projection call does not retain a
            # source-row transaction or connection.
            if crew_id is not None and extracted_data is not None:
                await certification_service.link_extracted_certificate(
                    crew_id=crew_id,
                    document_id=document_id,
                    extracted_data=extracted_data,
                    confidence=confidence,
                    expected_extracted_data=extracted_data,
                )
        finally:
            await dispose_engine()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.warning("Certificate projection reconciliation failed (%s)", type(exc).__name__)
        raise self.retry(exc=exc) from exc
    return {"document_id": document_id, "status": "reconciled"}


def queue_certificate_projection_reconcile(document_id: str) -> None:
    """Best-effort dispatch for a committed certificate awaiting linking."""
    try:
        reconcile_certificate_projection.delay(document_id)
    except Exception as exc:
        logger.warning(
            "Could not queue certificate projection reconciliation (%s)", type(exc).__name__
        )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def cleanup_deleted_crew_projections(
    self: Task,
    crew_id: str,
    document_ids: list[str],
) -> dict[str, str]:
    """Retry cache, profile-index, and document-vector cleanup after deletion."""
    import asyncio

    from app.database import dispose_engine
    from app.services.cache import cache_service
    from app.services.consultant_knowledge import consultant_knowledge_service

    async def _run() -> None:
        cache_cleanup_failed = False
        try:
            for cache_key in (
                cache_service._make_key("crew", crew_id),
                cache_service._make_key("summary", crew_id),
                cache_service._make_key("compliance", crew_id),
            ):
                if not await cache_service.delete(cache_key):
                    cache_cleanup_failed = True
            if not await consultant_knowledge_service.remove_from_index(crew_id):
                raise RuntimeError("crew search cleanup was not confirmed")
            if get_settings().ENABLE_SEMANTIC_SEARCH:
                from app.services.qdrant import qdrant_service

                for document_id in document_ids:
                    if not await qdrant_service.delete_document(document_id):
                        raise RuntimeError("crew document vector cleanup was not confirmed")
            if cache_cleanup_failed:
                raise RuntimeError("crew cache cleanup was not confirmed")
        finally:
            await dispose_engine()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.warning("Deleted crew projection cleanup failed (%s)", type(exc).__name__)
        raise self.retry(exc=exc) from exc
    return {"crew_id": crew_id, "status": "cleaned"}


def queue_deleted_crew_projection_cleanup(crew_id: str, document_ids: list[str]) -> None:
    """Best-effort dispatch for cleanup that outlives a deleted crew row."""
    try:
        cleanup_deleted_crew_projections.delay(crew_id, document_ids)
    except Exception as exc:
        logger.warning("Could not queue deleted crew cleanup (%s)", type(exc).__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def reconcile_crew_projection(self: Task, crew_id: str) -> dict[str, str]:
    """Retry the crew search projection from the current source row."""
    import asyncio

    from app.database import dispose_engine, get_session_factory
    from app.models import CrewMember
    from app.services.consultant_knowledge import consultant_knowledge_service

    async def _run() -> None:
        try:
            async with get_session_factory()() as session:
                crew = await session.get(CrewMember, crew_id)
            if crew is None or crew.publication_status != "approved":
                if not await consultant_knowledge_service.remove_from_index(crew_id):
                    raise RuntimeError("crew search cleanup was not confirmed")
            else:
                if not await consultant_knowledge_service.index_crew_member(crew):
                    raise RuntimeError("crew search reconciliation was not confirmed")
        finally:
            await dispose_engine()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.warning("Crew projection reconciliation failed (%s)", type(exc).__name__)
        raise self.retry(exc=exc) from exc
    return {"crew_id": crew_id, "status": "reconciled"}


def queue_crew_projection_reconcile(crew_id: str) -> None:
    """Best-effort dispatch for a crew projection provider outage."""
    try:
        reconcile_crew_projection.delay(crew_id)
    except Exception as exc:
        logger.warning("Could not queue crew projection reconciliation (%s)", type(exc).__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def cleanup_orphaned_upload(
    self: Task,
    storage_type: str,
    storage_path: str,
) -> dict[str, str]:
    """Retry removal of storage written by a losing idempotent upload."""
    import asyncio

    from app.services.upload import document_upload_service

    async def _run() -> None:
        remote_deleted = True
        if storage_type == "dropbox":
            remote_deleted = await document_upload_service.delete_from_dropbox(storage_path)
        document_upload_service.delete_file(storage_path)
        if not remote_deleted:
            raise RuntimeError("Dropbox orphan cleanup failed")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.warning("Orphaned upload cleanup failed (%s)", type(exc).__name__)
        raise self.retry(exc=exc) from exc
    return {"storage_path": storage_path, "status": "cleaned"}


def queue_orphaned_upload_cleanup(storage_type: str, storage_path: str) -> None:
    """Best-effort dispatch for a failed duplicate-upload cleanup."""
    try:
        cleanup_orphaned_upload.delay(storage_type, storage_path)
    except Exception as exc:
        logger.warning("Could not queue orphaned upload cleanup (%s)", type(exc).__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def cleanup_local_document_cache(
    self: Task,
    storage_path: str,
    resume_dropbox_document_id: str | None = None,
) -> dict[str, str]:
    """Retry removal of a managed local cache file after source deletion."""
    from app.services.upload import document_upload_service

    try:
        # A missing cache file is already clean; delete_file() only raises for
        # an actual filesystem failure that should be retried.
        document_upload_service.delete_file(storage_path)
        if resume_dropbox_document_id is not None:
            process_dropbox_document.delay(resume_dropbox_document_id)
    except Exception as exc:
        logger.warning("Local document cache cleanup failed (%s)", type(exc).__name__)
        raise self.retry(exc=exc) from exc
    return {"storage_path": storage_path, "status": "cleaned"}


def queue_local_document_cache_cleanup(
    storage_path: str,
    *,
    resume_dropbox_document_id: str | None = None,
) -> None:
    """Best-effort dispatch for cache cleanup after a committed deletion."""
    try:
        cleanup_local_document_cache.delay(storage_path, resume_dropbox_document_id)
    except Exception as exc:
        logger.warning("Could not queue local document cache cleanup (%s)", type(exc).__name__)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=10)
def process_document_extraction(self: Task, document_id: str) -> dict[str, Any]:
    """Process document extraction via LLM (synchronous for Celery).

    Args:
        document_id: UUID of the document to process.

    Returns:
        Dict with extraction results.
    """
    try:
        logger.info(f"Processing document extraction: {document_id}")
        result = sync_processor.process(document_id)
        _reconcile_document_search(document_id)
        _raise_for_retryable_failure(result)
        _maybe_queue_embeddings(document_id, str(result.get("status", "")))
        return result
    except Exception as exc:
        logger.error("Document extraction task failed (%s)", type(exc).__name__)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=10)
def process_dropbox_document(self: Task, document_id: str) -> dict[str, Any]:
    """Process a document from Dropbox.

    Args:
        document_id: UUID of the document to process.

    Returns:
        Dict with processing results.
    """
    try:
        logger.info(f"Processing Dropbox document: {document_id}")
        result = sync_processor.process(document_id)
        _reconcile_document_search(document_id)
        _raise_for_retryable_failure(result)
        _maybe_queue_embeddings(document_id, str(result.get("status", "")))
        return result
    except Exception as exc:
        logger.error("Dropbox processing task failed (%s)", type(exc).__name__)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def check_expiring_certifications(self: Task) -> dict[str, Any]:
    """Check for certifications expiring soon, update statuses, and emit alerts."""
    logger.info("Checking expiring certifications and evaluating compliance alerts")
    try:
        from app.services.compliance import compliance_service
        from app.services.sync_processor import get_sync_session

        session = get_sync_session()
        try:
            return compliance_service.evaluate_and_update_compliance_sync(session)
        finally:
            session.close()
    except Exception as e:
        logger.error("Certification check failed (%s)", type(e).__name__)
        # Returning a failed payload would acknowledge the Celery message as
        # successful, leaving expiration statuses and alerts stale until the
        # next daily beat. Retry transient database/provider failures instead.
        raise self.retry(exc=e) from e


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def index_document_embeddings(self: Task, document_id: str) -> dict[str, Any]:
    """Index document embeddings in Qdrant.

    Args:
        document_id: UUID of the document to index.
    """
    logger.info(f"Indexing embeddings for document: {document_id}")
    try:
        from app.services.sync_processor import get_sync_session

        session = get_sync_session()
        try:
            projection_input, reason = _load_document_projection_input(session, document_id)
            from app.services.qdrant import qdrant_service

            if projection_input is None:
                # Queued work can outlive deletion, rejection, unlinking, or
                # publication rollback. Remove any old point instead of
                # leaving an orphan searchable projection behind.
                if not qdrant_service.delete_document_sync(document_id):
                    queue_document_projection_cleanup(document_id)
                if reason == "not found":
                    return {"document_id": document_id, "status": "failed", "error": reason}
                return {"document_id": document_id, "status": "skipped", "reason": reason}
            indexable_text, metadata, _ = projection_input

            ok = qdrant_service.index_document_sync(
                document_id,
                indexable_text,
                metadata=metadata,
            )
            if not ok:
                # Do not retain a previous revision when the replacement could
                # not be written. A stale vector is worse than a temporary
                # search miss because it can surface withdrawn evidence.
                if not qdrant_service.delete_document_sync(document_id):
                    queue_document_projection_cleanup(document_id)
                raise RuntimeError("document embedding write was not confirmed")
            current_input, _ = _load_document_projection_input(session, document_id)
            if current_input != projection_input:
                if not qdrant_service.delete_document_sync(document_id):
                    queue_document_projection_cleanup(document_id)
                if current_input is not None and not _queue_embedding_reconcile(document_id):
                    raise RuntimeError("changed document embedding requeue was not confirmed")
                return {
                    "document_id": document_id,
                    "status": "skipped",
                    "reason": "document changed during indexing",
                }
            return {
                "document_id": document_id,
                "status": "indexed" if ok else "failed",
            }
        finally:
            session.close()
    except Exception as e:
        logger.error("Embedding indexing failed (%s)", type(e).__name__)
        raise self.retry(exc=e) from e
