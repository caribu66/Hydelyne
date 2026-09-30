from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import func, select

from app.auth.decorators import require_admin_rest
from app.config import get_settings
from app.database import get_session_factory
from app.domain.crew_accounts import is_contractor_profile
from app.domain.fields import normalize_classification
from app.models import Certification, CrewMember, CVReview, IncomingDocumentReview
from app.models import Document as DocumentModel
from app.services.audit import audit_service
from app.services.cache import cache_service
from app.services.dropbox_auth import (
    DropboxAuthError,
    download_dropbox_content,
    dropbox_request_json,
    token_provider,
)
from app.services.upload import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    document_upload_service,
    is_managed_dropbox_path,
)
from app.tasks.document_tasks import process_dropbox_document

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dropbox", tags=["dropbox"])
MAX_DROPBOX_WEBHOOK_BODY_BYTES = 64 * 1024
MAX_DROPBOX_WEBHOOK_ACCOUNTS = 100
MAX_DROPBOX_ACCOUNT_ID_LENGTH = 128
MAX_DROPBOX_WEBHOOK_CHALLENGE_LENGTH = 4096


class DropboxCursorUnavailable(RuntimeError):
    """Raised when the cursor store cannot determine the sync position."""


def _managed_dropbox_owner_id(owner: CrewMember | None) -> str | None:
    """Return only contractor-profile owners for managed Dropbox paths."""
    if owner is None or not is_contractor_profile(owner):
        return None
    return owner.id


async def _read_bounded_webhook_body(request: Request) -> bytes:
    """Read a signed webhook body without buffering an attacker-sized request."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_DROPBOX_WEBHOOK_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Webhook body too large")
        except ValueError:
            pass

    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > MAX_DROPBOX_WEBHOOK_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Webhook body too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_webhook_accounts(accounts: object) -> list[str]:
    """Bound webhook fan-out and reject malformed account identifiers."""
    if not isinstance(accounts, list):
        raise HTTPException(status_code=400, detail="Invalid accounts payload")
    if len(accounts) > MAX_DROPBOX_WEBHOOK_ACCOUNTS:
        raise HTTPException(status_code=400, detail="Too many Dropbox accounts")

    validated: list[str] = []
    for account_id in accounts:
        if (
            not isinstance(account_id, str)
            or not account_id
            or len(account_id) > MAX_DROPBOX_ACCOUNT_ID_LENGTH
        ):
            raise HTTPException(status_code=400, detail="Invalid Dropbox account identifier")
        validated.append(account_id)
    return validated


@router.get("/webhook")
async def dropbox_webhook_challenge(request: Request) -> PlainTextResponse:
    """Handle Dropbox webhook verification challenge."""
    challenge = request.query_params.get("challenge")
    if challenge:
        if len(challenge) > MAX_DROPBOX_WEBHOOK_CHALLENGE_LENGTH:
            raise HTTPException(status_code=400, detail="Challenge is too long")
        # Dropbox requires the challenge itself as a plain-text response body;
        # returning JSON makes webhook registration fail verification.
        return PlainTextResponse(
            challenge,
            headers={"X-Content-Type-Options": "nosniff"},
        )
    raise HTTPException(status_code=400, detail="No challenge provided")


@router.post("/webhook")
async def dropbox_webhook_handler(
    request: Request, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Handle Dropbox webhook notifications for file changes."""
    raw_body = await _read_bounded_webhook_body(request)
    signature = request.headers.get("X-Dropbox-Signature", "")
    # Webhooks authenticate with the provider signature before any side
    # effect. Without a configured secret there is nothing to verify against,
    # so the endpoint is unavailable in every environment — silently queuing
    # sync work for unauthenticated requests is not an option even in dev.
    if not settings.DROPBOX_APP_SECRET:
        raise HTTPException(status_code=503, detail="Dropbox webhook not configured")
    expected = hmac.new(
        settings.DROPBOX_APP_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid signature")

    import json as _json

    try:
        body = _json.loads(raw_body.decode() or "{}")
    except _json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be an object")
    logger.info("Dropbox webhook received")

    list_folder = body.get("list_folder", {})
    if not isinstance(list_folder, dict):
        raise HTTPException(status_code=400, detail="Invalid list_folder payload")
    accounts = _validate_webhook_accounts(list_folder.get("accounts", []))

    for account_id in accounts:
        background_tasks.add_task(process_dropbox_account, account_id)

    return {"status": "ok"}


async def process_dropbox_account(account_id: str) -> None:
    """Process file changes for a Dropbox account."""
    try:
        cursor = await get_dropbox_cursor(account_id)
        if cursor:
            await continue_dropbox_listing(account_id, cursor)
        else:
            await start_dropbox_listing(account_id)
    except DropboxCursorUnavailable:
        logger.warning("Could not read Dropbox cursor; deferring account sync")
    except Exception as exc:
        logger.error(
            "Failed to process Dropbox account %s (%s)", account_id, type(exc).__name__
        )


async def get_dropbox_cursor(account_id: str) -> Optional[str]:
    """Get the stored cursor for an account (Redis-backed)."""
    try:
        key = f"dropbox:cursor:{account_id}"
        redis = await cache_service._get_redis()
        value = await redis.get(key)
        return value if isinstance(value, str) else None
    except Exception as exc:
        logger.warning("Failed to read Dropbox cursor (%s)", type(exc).__name__)
        raise DropboxCursorUnavailable from exc


async def start_dropbox_listing(account_id: str) -> None:
    """Start listing files from Dropbox root."""
    if not token_provider.configured:
        logger.warning("Dropbox is not configured, skipping listing")
        return
    async with httpx.AsyncClient(timeout=30.0) as client:
        status_code, data = await dropbox_request_json(
            client,
            "POST",
            "https://api.dropboxapi.com/2/files/list_folder",
            headers={"Content-Type": "application/json"},
            json={
                "path": "",
                "recursive": True,
                "include_media_info": False,
                "include_deleted": True,
                "include_has_explicit_shared_members": False,
                "include_mounted_folders": True,
                "limit": 100,
            },
        )
        if status_code == 200 and data is not None:
            await process_dropbox_entries(data.get("entries", []))
            await save_dropbox_cursor(account_id, data.get("cursor"))
            # Handle pagination
            while data.get("has_more"):
                cursor = data.get("cursor")
                if not cursor:
                    break
                status_code, data = await dropbox_request_json(
                    client,
                    "POST",
                    "https://api.dropboxapi.com/2/files/list_folder/continue",
                    headers={"Content-Type": "application/json"},
                    json={"cursor": cursor},
                )
                if status_code != 200 or data is None:
                    break
                await process_dropbox_entries(data.get("entries", []))
                await save_dropbox_cursor(account_id, data.get("cursor"))
        else:
            logger.error("Dropbox list_folder failed with status %s", status_code)


async def continue_dropbox_listing(account_id: str, cursor: str) -> None:
    """Continue listing files from a cursor."""
    if not token_provider.configured:
        return
    async with httpx.AsyncClient(timeout=30.0) as client:
        status_code, data = await dropbox_request_json(
            client,
            "POST",
            "https://api.dropboxapi.com/2/files/list_folder/continue",
            headers={"Content-Type": "application/json"},
            json={"cursor": cursor},
        )
        if status_code == 409:
            # Dropbox invalidates cursors after retention/namespace changes.
            # Retrying the same cursor forever otherwise permanently stalls
            # webhook ingestion for this account.
            logger.warning("Dropbox cursor reset requested; restarting account listing")
            await start_dropbox_listing(account_id)
            return
        if status_code == 200 and data is not None:
            await process_dropbox_entries(data.get("entries", []))
            await save_dropbox_cursor(account_id, data.get("cursor"))
            while data.get("has_more"):
                next_cursor = data.get("cursor")
                if not isinstance(next_cursor, str) or not next_cursor:
                    break
                cursor = next_cursor
                status_code, data = await dropbox_request_json(
                    client,
                    "POST",
                    "https://api.dropboxapi.com/2/files/list_folder/continue",
                    headers={"Content-Type": "application/json"},
                    json={"cursor": cursor},
                )
                if status_code == 409:
                    logger.warning(
                        "Dropbox cursor reset during pagination; restarting account listing"
                    )
                    await start_dropbox_listing(account_id)
                    return
                if status_code != 200 or data is None:
                    break
                await process_dropbox_entries(data.get("entries", []))
                await save_dropbox_cursor(account_id, data.get("cursor"))


async def process_dropbox_entries(entries: list[dict]) -> None:
    """Process Dropbox file entries."""
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get(".tag") == "file":
            await process_dropbox_file(entry)
        elif entry.get(".tag") == "deleted":
            await process_dropbox_deletion(entry.get("path_lower", ""))


async def process_dropbox_deletion(file_path: str) -> None:
    """Remove a record for content deleted outside the application."""
    if not isinstance(file_path, str) or not is_managed_dropbox_path(file_path):
        return
    async with get_session_factory()() as session:
        result = await session.execute(
            select(DocumentModel)
            .where(func.lower(DocumentModel.dropbox_path) == file_path.lower())
            .with_for_update()
        )
        doc = result.scalar_one_or_none()
        if doc:
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
            if doc.crew_member_id:
                from app.services.certification_projection import (
                    reconcile_medical_profile_after_detachment,
                )

                await reconcile_medical_profile_after_detachment(
                    session,
                    crew_id=doc.crew_member_id,
                    detached_certification_ids=detached_certification_ids,
                    detached_expiry_dates=detached_expiry_dates,
                )
            deleted_document_id = doc.id
            deleted_crew_id = doc.crew_member_id
            deleted_storage_path = doc.storage_path
            await session.delete(doc)
            await session.commit()
            cleanup_required = False
            if deleted_crew_id:
                for cache_key in (
                    cache_service._make_key("compliance", deleted_crew_id),
                    cache_service._make_key("summary", deleted_crew_id),
                ):
                    try:
                        if not await cache_service.delete(cache_key):
                            cleanup_required = True
                            logger.warning("Deleted document cache invalidation was not confirmed")
                    except Exception as exc:
                        cleanup_required = True
                        logger.warning(
                            "Could not clear deleted document cache (%s)", type(exc).__name__
                        )
            try:
                document_upload_service.delete_file(deleted_storage_path)
            except Exception as exc:
                cleanup_required = True
                logger.warning("Could not remove deleted Dropbox cache (%s)", type(exc).__name__)
                from app.tasks.document_tasks import queue_local_document_cache_cleanup

                queue_local_document_cache_cleanup(deleted_storage_path)
            from app.services.consultant_knowledge import consultant_knowledge_service

            # Dropbox deletion is an external source-of-truth change. Remove
            # the derived document-search projection after the database commit
            # so deleted evidence cannot remain discoverable through Meili.
            try:
                if not await consultant_knowledge_service.reconcile_document_index(
                    deleted_document_id
                ):
                    cleanup_required = True
                    logger.warning("Deleted document search cleanup was not confirmed")
            except Exception as exc:
                cleanup_required = True
                logger.warning(
                    "Could not remove deleted document search projection (%s)", type(exc).__name__
                )
            if settings.ENABLE_SEMANTIC_SEARCH:
                try:
                    from app.services.qdrant import qdrant_service

                    if not await qdrant_service.delete_document(deleted_document_id):
                        cleanup_required = True
                        logger.warning("Deleted document vector cleanup was not confirmed")
                except Exception as exc:
                    cleanup_required = True
                    logger.warning(
                        "Could not remove deleted document embedding (%s)", type(exc).__name__
                    )
            if cleanup_required:
                from app.tasks.document_tasks import queue_document_projection_cleanup

                queue_document_projection_cleanup(deleted_document_id)


async def process_dropbox_file(file_entry: dict) -> None:
    """Process a single Dropbox file."""
    if not isinstance(file_entry, dict):
        return
    file_path = file_entry.get("path_lower", "")
    file_name = file_entry.get("name", "")
    if not isinstance(file_path, str) or not file_path or not isinstance(file_name, str):
        return
    # Only ingest files created inside the application's managed root. Without
    # this boundary, any supported file elsewhere in the connected Dropbox
    # account becomes an orphan document row with no crew owner.
    if not is_managed_dropbox_path(file_path):
        return

    revision = file_entry.get("rev")
    file_size = file_entry.get("size")
    if (
        len(file_name) > 255
        or (revision is not None and (not isinstance(revision, str) or len(revision) > 100))
        or (
            not isinstance(file_size, int)
            or isinstance(file_size, bool)
            or not 0 <= file_size <= MAX_FILE_SIZE
        )
    ):
        return

    if not any(file_name.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
        return

    async with get_session_factory()() as session:
        existing = await session.execute(
            select(DocumentModel)
            .where(func.lower(DocumentModel.dropbox_path) == file_path.lower())
            .with_for_update()
        )
        doc = existing.scalar_one_or_none()
        if doc:
            if doc.crew_member_id:
                owner = (
                    await session.execute(
                        select(CrewMember)
                        .where(CrewMember.id == doc.crew_member_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if owner is None or not is_contractor_profile(owner):
                    return
            # Dropbox sends a new revision for a modified file.  Requeue it
            # rather than silently serving stale extracted metadata.
            if doc.dropbox_revision != file_entry.get("rev"):
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
                if doc.crew_member_id:
                    from app.services.certification_projection import (
                        reconcile_medical_profile_after_detachment,
                    )

                    await reconcile_medical_profile_after_detachment(
                        session,
                        crew_id=doc.crew_member_id,
                        detached_certification_ids=detached_certification_ids,
                        detached_expiry_dates=detached_expiry_dates,
                    )
                if normalize_classification(doc.classification) == "cv":
                    review = (
                        await session.execute(
                            select(CVReview).where(CVReview.document_id == doc.id)
                        )
                    ).scalar_one_or_none()
                    if review is not None:
                        crew = (
                            await session.get(CrewMember, doc.crew_member_id)
                            if doc.crew_member_id
                            else None
                        )
                        review.status = "awaiting_review"
                        review.prior_publication_status = (
                            crew.publication_status if crew else "draft"
                        )
                        review.proposed_data = None
                        review.approved_data = None
                        review.reviewed_by = None
                        review.review_note = None
                        review.reviewed_at = None
                if doc.uploaded_by == "contractor-upload-link":
                    incoming_review = (
                        await session.execute(
                            select(IncomingDocumentReview).where(
                                IncomingDocumentReview.document_id == doc.id
                            )
                        )
                    ).scalar_one_or_none()
                    if incoming_review is not None:
                        incoming_review.status = "unread"
                        incoming_review.claimed_by = None
                        incoming_review.claimed_at = None
                        incoming_review.resolved_at = None
                doc.dropbox_revision = file_entry.get("rev")
                doc.file_size = file_size
                doc.extracted_data = None
                doc.extracted_text = None
                doc.extraction_confidence = None
                doc.extraction_status = "pending"
                await session.commit()
                cleanup_required = False
                if doc.crew_member_id:
                    for cache_key in (
                        cache_service._make_key("compliance", doc.crew_member_id),
                        cache_service._make_key("summary", doc.crew_member_id),
                    ):
                        try:
                            if not await cache_service.delete(cache_key):
                                cleanup_required = True
                                logger.warning(
                                    "Revised document cache invalidation was not confirmed"
                                )
                        except Exception as exc:
                            cleanup_required = True
                            logger.warning(
                                "Could not clear revised document cache (%s)", type(exc).__name__
                            )
                # The Dropbox path remains stable across revisions, while the
                # local cache filename is document-based. Remove the old
                # cached bytes before extraction or admin download can read
                # them instead of fetching the new Dropbox revision.
                cache_cleanup_pending = False
                try:
                    document_upload_service.delete_file(doc.storage_path)
                except Exception as exc:
                    cache_cleanup_pending = True
                    cleanup_required = True
                    logger.warning(
                        "Could not remove revised Dropbox cache (%s)", type(exc).__name__
                    )
                    from app.tasks.document_tasks import queue_local_document_cache_cleanup

                    queue_local_document_cache_cleanup(
                        doc.storage_path,
                        resume_dropbox_document_id=doc.id,
                    )
                from app.services.consultant_knowledge import consultant_knowledge_service

                # The old extracted projection is no longer authoritative once
                # a new Dropbox revision enters processing.
                try:
                    projection_reconciled = (
                        await consultant_knowledge_service.reconcile_document_index(doc.id)
                    )
                except Exception as exc:
                    cleanup_required = True
                    # Derived search cleanup must not prevent the new source
                    # revision from entering extraction. The committed
                    # pending state remains authoritative and can be repaired
                    # by a later projection retry.
                    logger.warning(
                        "Could not reconcile Dropbox revision projection (%s)",
                        type(exc).__name__,
                    )
                else:
                    if not projection_reconciled:
                        cleanup_required = True
                        logger.warning("Dropbox revision projection cleanup was not confirmed")
                finally:
                    if settings.ENABLE_SEMANTIC_SEARCH:
                        from app.services.qdrant import qdrant_service

                        try:
                            if not await qdrant_service.delete_document(doc.id):
                                cleanup_required = True
                                logger.warning("Dropbox revision vector cleanup was not confirmed")
                        except Exception as exc:
                            cleanup_required = True
                            logger.warning(
                                "Could not remove Dropbox revision vector (%s)",
                                type(exc).__name__,
                            )
                if cleanup_required:
                    from app.tasks.document_tasks import queue_document_projection_cleanup

                    queue_document_projection_cleanup(doc.id)
                if not cache_cleanup_pending:
                    try:
                        process_dropbox_document.delay(doc.id)
                    except Exception as exc:
                        logger.warning(
                            "Could not queue Dropbox revision extraction (%s)", type(exc).__name__
                        )
                        current = (
                            await session.execute(
                                select(DocumentModel)
                                .where(DocumentModel.id == doc.id)
                                .with_for_update()
                            )
                        ).scalar_one_or_none()
                        if current is not None and current.extraction_status == "pending":
                            current.extraction_status = "failed"
                            await session.commit()
            return

        # App-managed files live at /hydenlyne/<crew_id>/documents/... —
        # recover the owner so the row joins the staff review queue instead
        # of becoming a crew-less orphan visible only to admins.
        crew_member_id: Optional[str] = None
        parts = file_path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "hydenlyne":
            candidate = parts[1]
            owner_result = await session.execute(
                select(CrewMember).where(CrewMember.id == candidate).with_for_update()
            )
            crew_member_id = _managed_dropbox_owner_id(owner_result.scalar_one_or_none())

        doc = DocumentModel(
            file_name=file_name,
            file_type=file_name.split(".")[-1].lower(),
            file_size=file_size,
            crew_member_id=crew_member_id,
            storage_type="dropbox",
            storage_path=file_path,
            dropbox_path=file_path,
            dropbox_revision=file_entry.get("rev"),
            extraction_status="pending",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        queued = True
        try:
            process_dropbox_document.delay(doc.id)
        except Exception as exc:
            queued = False
            logger.warning("Could not queue new Dropbox extraction (%s)", type(exc).__name__)
            current = (
                await session.execute(
                    select(DocumentModel).where(DocumentModel.id == doc.id).with_for_update()
                )
            ).scalar_one_or_none()
            if current is not None and current.extraction_status == "pending":
                current.extraction_status = "failed"
                await session.commit()
        logger.info("New managed Dropbox document %s", "queued" if queued else "left retryable")


async def save_dropbox_cursor(account_id: str, cursor: Optional[str]) -> None:
    """Save the cursor for an account (Redis)."""
    if not cursor:
        return
    try:
        key = f"dropbox:cursor:{account_id}"
        redis = await cache_service._get_redis()
        await redis.set(key, cursor)
    except Exception as exc:
        logger.warning("Failed to save Dropbox cursor (%s)", type(exc).__name__)


@router.post("/download/{document_id}")
async def download_dropbox_file(
    document_id: str,
    request: Request,
    current_user: CrewMember = Depends(require_admin_rest),
) -> StreamingResponse:
    """Download a file from Dropbox by document ID. T3 (admin) only — C3 bytes."""
    async with get_session_factory()() as session:
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc or doc.storage_type != "dropbox":
            raise HTTPException(status_code=404, detail="Document not found")
        if not doc.dropbox_path or not is_managed_dropbox_path(doc.dropbox_path):
            raise HTTPException(status_code=404, detail="Document not found")

        # Audit log: record access. C3 bytes must never leave without an audit
        # entry, so an audit-write failure fails the download (retryable 503)
        # instead of serving unlogged evidence.
        try:
            await audit_service.log_access(document_id, current_user.id, "download")
        except Exception as exc:
            logger.warning("Audit log failed for Dropbox download (%s)", type(exc).__name__)
            raise HTTPException(
                status_code=503, detail="Download audit unavailable; try again"
            ) from exc

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                status_code, content = await download_dropbox_content(
                    client,
                    "POST",
                    "https://content.dropboxapi.com/2/files/download",
                    max_bytes=MAX_FILE_SIZE,
                    headers={"Dropbox-API-Arg": json.dumps({"path": doc.dropbox_path})},
                )
            except DropboxAuthError as exc:
                logger.error(
                    "Dropbox auth unavailable for download (%s)", type(exc).__name__
                )
                raise HTTPException(status_code=503, detail="Dropbox storage is unavailable")
            if status_code == 200 and content is not None:
                valid, validation_error = document_upload_service.validate_file_content(
                    doc.file_name, content
                )
                if not valid:
                    logger.warning(
                        "Refusing Dropbox download after content validation failure (%s)",
                        validation_error,
                    )
                    raise HTTPException(
                        status_code=422, detail="Stored document failed validation"
                    )
                from app.api.documents import _content_disposition

                return StreamingResponse(
                    iter([content]),
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": _content_disposition(doc.file_name)},
                )
            raise HTTPException(status_code=status_code, detail="Download failed")
