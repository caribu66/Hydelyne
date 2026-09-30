from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.decorators import (
    require_admin_rest,
    require_api_key,
    require_staff_rest,
)
from app.database import get_session_factory
from app.domain.crew_accounts import is_contractor_profile
from app.domain.fields import normalize_classification
from app.models import Certification, CrewMember, CVReview, DocumentRequest, IncomingDocumentReview
from app.models import Document as DocumentModel
from app.services.audit import audit_service
from app.services.cache import cache_service
from app.services.document_requests import document_request_service
from app.services.upload import (
    CHUNK_SIZE,
    MAX_FILE_SIZE,
    DropboxStorageError,
    document_upload_service,
    safe_path_component,
)
from app.tasks.document_tasks import process_document_extraction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _parse_optional_form_date(value: str | None, field: str) -> date | None:
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid {field}; expected YYYY-MM-DD"
        ) from exc


async def _cleanup_saved_upload(storage_type: str | None, storage_path: str | None) -> None:
    """Remove a file that was saved before its database write failed."""
    if not storage_path:
        return
    if storage_type == "dropbox" and storage_path.startswith("/hydenlyne/"):
        if not await document_upload_service.delete_from_dropbox(storage_path):
            logger.warning("Could not clean up an untracked Dropbox upload")
            from app.tasks.document_tasks import queue_orphaned_upload_cleanup

            queue_orphaned_upload_cleanup(storage_type, storage_path)
        try:
            document_upload_service.delete_file(storage_path)
        except Exception as exc:
            logger.warning("Could not clean up local upload cache (%s)", type(exc).__name__)
            from app.tasks.document_tasks import queue_local_document_cache_cleanup

            queue_local_document_cache_cleanup(storage_path)
        return
    try:
        document_upload_service.delete_file(storage_path)
    except Exception as exc:
        logger.warning("Could not clean up local upload cache (%s)", type(exc).__name__)
        from app.tasks.document_tasks import queue_local_document_cache_cleanup

        queue_local_document_cache_cleanup(storage_path)


def _content_disposition(filename: str | None) -> str:
    """Build a header-safe Content-Disposition value (RFC 6266/5987).

    Stored file names are raw client input: quotes, semicolons, or newlines
    would break out of `filename="..."`. Emit a sanitized ASCII fallback
    plus the RFC 5987 `filename*` UTF-8 form.
    """
    from urllib.parse import quote

    original = filename or "download"
    safe = re.sub(r"[^A-Za-z0-9.\- ]", "_", original).strip()[:100] or "download"
    return f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(original, safe='')}"


async def _retry_failed_idempotent_document(session: AsyncSession, document: DocumentModel) -> str:
    """Requeue a document whose prior broker dispatch failed."""
    if document.extraction_status != "failed":
        return document.extraction_status
    document.extraction_status = "pending"
    await session.commit()
    try:
        process_document_extraction.delay(document.id)
        return "pending"
    except Exception as exc:
        current = (
            await session.execute(
                select(DocumentModel).where(DocumentModel.id == document.id).with_for_update()
            )
        ).scalar_one_or_none()
        if current is not None and current.extraction_status == "pending":
            current.extraction_status = "failed"
            await session.commit()
        logger.warning("Could not retry idempotent extraction (%s)", type(exc).__name__)
        return "failed"


async def _lock_active_document_request(session: AsyncSession, request_id: str) -> DocumentRequest:
    """Recheck a bearer upload request immediately before reusing its record."""
    from sqlalchemy import select

    current_request = (
        await session.execute(
            select(DocumentRequest).where(DocumentRequest.id == request_id).with_for_update()
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if current_request is None:
        raise HTTPException(status_code=404, detail="This upload link is invalid or has expired")
    expires_at = current_request.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if current_request.status != "active" or expires_at <= now:
        if current_request.status == "active":
            current_request.status = "expired"
            await session.commit()
        raise HTTPException(status_code=404, detail="This upload link is invalid or has expired")
    crew = (
        await session.execute(
            select(CrewMember)
            .where(CrewMember.id == current_request.crew_member_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if crew is None or not is_contractor_profile(crew) or crew.publication_status == "rejected":
        raise HTTPException(status_code=404, detail="This upload link is invalid or has expired")
    return current_request


@router.get("/request/{token}")
async def get_document_request(token: str) -> dict[str, str]:
    """Return a deliberately minimal public upload-request description."""
    request = await document_request_service.get_active_request(token)
    if request is None:
        raise HTTPException(status_code=404, detail="This upload link is invalid or has expired")
    expires_at = request.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return {"status": "active", "expires_at": expires_at.isoformat()}


@router.post("/request/{token}/upload")
async def upload_requested_document(
    token: str,
    file: UploadFile = File(...),
    classification: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Form(None),
) -> dict[str, Any]:
    """Accept a contractor upload only through a valid, expiring bearer link."""
    request = await document_request_service.get_active_request(token)
    if request is None:
        raise HTTPException(status_code=404, detail="This upload link is invalid or has expired")
    is_valid, error_msg = document_upload_service.validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    safe_file_name = file.filename or "upload"
    if idempotency_key is None or not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", idempotency_key):
        raise HTTPException(status_code=400, detail="A valid upload idempotency key is required")
    if classification is not None:
        try:
            classification = normalize_classification(classification)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid document category") from exc
        if classification == "cv":
            raise HTTPException(
                status_code=403,
                detail="CVs must use the staff upload and administrator review workflow",
            )
    upload_key = f"request:{request.id}:{idempotency_key}"
    from sqlalchemy import select as _select

    async with get_session_factory()() as session:
        await _lock_active_document_request(session, request.id)
        existing = (
            await session.execute(
                _select(DocumentModel).where(DocumentModel.upload_key == upload_key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            retry_status = await _retry_failed_idempotent_document(session, existing)
            return {
                "id": existing.id,
                "file_name": existing.file_name,
                "status": retry_status,
            }

    saved_storage_path: str | None = None
    saved_storage_type: str | None = None
    try:
        document_id, storage_path, file_size = await document_upload_service.save_file(
            file, request.crew_member_id, classification
        )
        file_type = document_upload_service.get_file_type(safe_file_name)
        storage_type = "dropbox" if storage_path.startswith("/hydenlyne/") else "local"
        saved_storage_path = storage_path
        saved_storage_type = storage_type
        async with get_session_factory()() as session:
            # The initial bearer-token lookup happens before file I/O. Recheck
            # under a row lock immediately before persistence so a slow upload
            # cannot complete after the request expires or is revoked.
            current_request = await _lock_active_document_request(session, request.id)
            current_crew = (
                await session.execute(
                    _select(CrewMember)
                    .where(CrewMember.id == current_request.crew_member_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if (
                current_crew is None
                or not is_contractor_profile(current_crew)
                or current_crew.publication_status == "rejected"
            ):
                raise HTTPException(
                    status_code=404, detail="This upload link is invalid or has expired"
                )
            doc = DocumentModel(
                id=document_id,
                crew_member_id=request.crew_member_id,
                file_name=safe_file_name,
                file_type=file_type,
                file_size=file_size,
                storage_type=storage_type,
                storage_path=storage_path,
                dropbox_path=storage_path if storage_type == "dropbox" else None,
                classification=classification,
                extraction_status="pending",
                upload_key=upload_key,
                uploaded_by="contractor-upload-link",
            )
            session.add(doc)
            try:
                # Same FK-only ordering constraint as the CV path below: flush
                # the parent row before the child review row (see comment there).
                # Keep the flush inside the recovery block because a concurrent
                # idempotent retry raises its unique-key error here, not at
                # commit time.
                await session.flush()
                session.add(IncomingDocumentReview(request_id=request.id, document_id=document_id))
                await session.commit()
            except IntegrityError:
                # Concurrent uploads with the same idempotency key: roll back and return existing
                await session.rollback()
                existing = (
                    await session.execute(
                        _select(DocumentModel).where(DocumentModel.upload_key == upload_key)
                    )
                ).scalar_one_or_none()
                if existing is None:
                    raise
                await _cleanup_saved_upload(storage_type, storage_path)
                return {
                    "id": existing.id,
                    "file_name": existing.file_name,
                    "status": existing.extraction_status,
                }

        dispatch_status = "pending"
        try:
            process_document_extraction.delay(document_id)
        except Exception:
            logger.warning("Could not queue contractor document extraction")
            dispatch_status = "failed"
            async with get_session_factory()() as session:
                doc = (
                    await session.execute(
                        _select(DocumentModel)
                        .where(DocumentModel.id == document_id)
                        .with_for_update()
                    )
                ).scalar_one()
                if doc.extraction_status == "pending":
                    doc.extraction_status = "failed"
                    # The review row committed above would otherwise linger as
                    # `unread` in the staff queue for a document that can never
                    # be processed. Mark it terminal alongside the document.
                    review = (
                        await session.execute(
                            _select(IncomingDocumentReview)
                            .where(IncomingDocumentReview.document_id == document_id)
                            .with_for_update()
                        )
                    ).scalar_one_or_none()
                    if review is not None and review.status in ("unread", "claimed"):
                        review.status = "failed"
                    await session.commit()
        return {
            "id": document_id,
            "file_name": safe_file_name,
            "status": dispatch_status,
        }
    except HTTPException:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        raise
    except DropboxStorageError as exc:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        raise HTTPException(
            status_code=503, detail="Document storage is temporarily unavailable"
        ) from exc
    except ValueError as exc:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        logger.error("Contractor document upload failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Upload failed") from exc


@router.post("/requests")
async def create_document_request(
    crew_id: str = Form(...),
    expires_in_days: int = Form(14),
    current_user: CrewMember = Depends(require_staff_rest),
) -> dict[str, str]:
    """Create a contractor upload link. The bearer token is returned once only."""
    if not 1 <= expires_in_days <= 30:
        raise HTTPException(status_code=400, detail="Expiry must be between 1 and 30 days")
    try:
        created = await document_request_service.create(
            crew_id=crew_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            expires_in_days=expires_in_days,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"token": created.token, "expires_at": created.expires_at.isoformat()}


@router.get("/review-queue")
async def list_incoming_document_reviews(
    current_user: CrewMember = Depends(require_staff_rest),
) -> list[dict[str, Any]]:
    """Return durable contractor-upload queue items to authorized staff."""
    async with get_session_factory()() as session:
        query = (
            select(IncomingDocumentReview, DocumentModel, CrewMember)
            .join(DocumentModel, IncomingDocumentReview.document_id == DocumentModel.id)
            .join(CrewMember, DocumentModel.crew_member_id == CrewMember.id)
            .where(
                IncomingDocumentReview.status.in_(["unread", "claimed"]),
                CrewMember.password_hash.is_(None),
                or_(CrewMember.role.is_(None), CrewMember.role.not_in(("staff", "admin"))),
            )
        )
        if current_user.role != "admin":
            query = query.where(
                or_(
                    CrewMember.publication_status == "approved",
                    and_(
                        CrewMember.publication_status == "draft",
                        CrewMember.submitted_by == current_user.id,
                    ),
                )
            )
        rows = await session.execute(
            query.order_by(
                IncomingDocumentReview.created_at.desc(), IncomingDocumentReview.id.desc()
            )
            .limit(100)
            .with_for_update()
        )
        return [
            {
                "id": review.id,
                "status": review.status,
                "document_id": document.id,
                "file_name": document.file_name,
                "file_type": document.file_type,
                "file_size": document.file_size,
                "classification": document.classification,
                "extraction_status": document.extraction_status,
                "crew_member_id": crew.id,
                "contractor_name": crew.full_name,
                "created_at": review.created_at.isoformat(),
                "claimed_by": review.claimed_by,
            }
            for review, document, crew in rows.all()
        ]


@router.post("/review-queue/{review_id}/action")
async def review_incoming_document(
    review_id: str,
    action: str = Form(...),
    note: Optional[str] = Form(None),
    current_user: CrewMember = Depends(require_staff_rest),
) -> dict[str, Any]:
    """Approve or reject a contractor-uploaded document by review queue ID."""
    try:
        review, doc = await document_request_service.resolve_review(
            review_id=review_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action=action,
            note=note,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "id": review.id if review else None,
        "status": review.status if review else doc.extraction_status,
        "extraction_status": doc.extraction_status,
        "document_id": doc.id,
        "claimed_by": review.claimed_by if review else current_user.id,
        "resolved_at": (review.resolved_at.isoformat() if review and review.resolved_at else None),
    }


@router.post("/{document_id}/review")
async def review_document_by_id(
    document_id: str,
    action: str = Form(...),
    note: Optional[str] = Form(None),
    current_user: CrewMember = Depends(require_staff_rest),
) -> dict[str, Any]:
    """Approve or reject a document directly by document ID, resolving any active review queue item."""
    try:
        review, doc = await document_request_service.resolve_review(
            document_id=document_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action=action,
            note=note,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "id": review.id if review else None,
        "status": review.status if review else doc.extraction_status,
        "extraction_status": doc.extraction_status,
        "document_id": doc.id,
        "claimed_by": review.claimed_by if review else current_user.id,
        "resolved_at": (review.resolved_at.isoformat() if review and review.resolved_at else None),
    }


@router.post("/preview-cv")
async def preview_cv(
    file: UploadFile = File(...),
    current_user: CrewMember = Depends(require_staff_rest),
) -> dict[str, Any]:
    """Extract CV identity fields before a crew record is created.

    This is intentionally a preview only: it never stores the uploaded bytes
    or creates database metadata. The subsequent document upload remains the
    single operation that writes the approved CV to Dropbox.

    No LLM call — uses the same deterministic PDF-table extractor as the
    main CV pipeline (see backend/docs/consultant-knowledge-core.md). This
    template never carries email/phone at all, so those two are always
    None here; the operator fills them in by hand. A non-PDF CV also
    returns empty fields (the table parser is PDF-only) rather than
    falling back to AI.
    """
    empty_result = {"full_name": None, "email": None, "phone": None, "nationality": None}

    suffix = Path(file.filename or "cv.pdf").suffix.lower()
    temp_path = None
    try:
        is_valid, error_msg = document_upload_service.validate_file(file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_path = temp_file.name
            total_size = 0
            header = b""
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File exceeds maximum size of {MAX_FILE_SIZE} bytes",
                    )
                if len(header) < 16:
                    header += chunk[: 16 - len(header)]
                temp_file.write(chunk)

        is_valid, error_msg = document_upload_service.validate_file(file, header)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        file_type = document_upload_service.get_file_type(file.filename or "cv.pdf")
        if file_type != "pdf":
            return empty_result

        from app.services.cv_table_extractor import extract_cv_tables

        table_extraction = await asyncio.to_thread(extract_cv_tables, temp_path)
        personal = table_extraction.personal.fields if table_extraction.personal else {}
        return {
            "full_name": table_extraction.full_name,
            "email": None,
            "phone": None,
            "nationality": personal.get("NATIONALITY"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("CV preview extraction failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=422, detail="Could not read identity details from this CV")
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


@router.post("/upload")
async def upload_document(
    request: Request,
    crew_id: str = Form(...),
    file: UploadFile = File(...),
    classification: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Form(None),
    issue_date: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    current_user: CrewMember = Depends(require_staff_rest),
) -> dict[str, Any]:
    """Upload a document, with staff limited to their own CV draft workflow."""
    is_valid, error_msg = document_upload_service.validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    safe_file_name = file.filename or "upload"
    parsed_issue_date = _parse_optional_form_date(issue_date, "issue_date")
    parsed_expiry_date = _parse_optional_form_date(expiry_date, "expiry_date")
    if parsed_issue_date and parsed_expiry_date and parsed_expiry_date < parsed_issue_date:
        raise HTTPException(status_code=400, detail="expiry_date must be on or after issue_date")
    clean_notes = notes.strip() if notes and notes.strip() else None
    if clean_notes and len(clean_notes) > 5000:
        raise HTTPException(status_code=400, detail="notes must be 5000 characters or fewer")
    clean_title = title.strip() if title and title.strip() else None
    if clean_title and len(clean_title) > 255:
        raise HTTPException(status_code=400, detail="title must be 255 characters or fewer")
    # Normalize once so storage, CV gating, and downstream filters agree.
    try:
        classification = (
            normalize_classification(classification) if classification is not None else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document category") from exc
    try:
        crew_id = safe_path_component(crew_id, "crew_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if idempotency_key is not None and not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key):
        raise HTTPException(status_code=400, detail="Invalid upload idempotency key")

    from sqlalchemy import select as _select

    async with get_session_factory()() as _sess:
        crew = (
            await _sess.execute(
                _select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
            )
        ).scalar_one_or_none()
        if crew is None:
            raise HTTPException(status_code=404, detail="Crew member not found")
        if not is_contractor_profile(crew):
            raise HTTPException(status_code=404, detail="Crew member not found")
        if current_user.role != "admin":
            if classification != "cv":
                raise HTTPException(
                    status_code=403,
                    detail="Manual document uploads require administrator access",
                )
            if crew.publication_status != "draft" or crew.submitted_by != current_user.id:
                raise HTTPException(status_code=403, detail="This draft belongs to another user")
        draft_values = {
            "full_name": crew.full_name,
            "email": crew.email,
            "phone": crew.phone,
            "nationality": crew.nationality,
        }
        if idempotency_key:
            existing = (
                await _sess.execute(
                    _select(DocumentModel).where(DocumentModel.upload_key == idempotency_key)
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.uploaded_by == "agent":
                    raise HTTPException(status_code=409, detail="Upload key already used")
                if existing.crew_member_id != crew_id:
                    raise HTTPException(status_code=409, detail="Upload key already used")
                retry_status = await _retry_failed_idempotent_document(_sess, existing)
                return {
                    "id": existing.id,
                    "file_name": existing.file_name,
                    "file_type": existing.file_type,
                    "file_size": existing.file_size,
                    "status": retry_status,
                    "storage_type": existing.storage_type,
                }

    saved_storage_path: str | None = None
    saved_storage_type: str | None = None
    try:
        document_id, storage_path, file_size = await document_upload_service.save_file(
            file, crew_id, classification
        )
        file_type = document_upload_service.get_file_type(safe_file_name)

        # Determine storage type based on path
        storage_type = "dropbox" if storage_path.startswith("/hydenlyne/") else "local"
        dropbox_path = storage_path if storage_type == "dropbox" else None
        saved_storage_path = storage_path
        saved_storage_type = storage_type

        async with get_session_factory()() as session:
            # The authorization check above protects the start of the upload,
            # but file storage can take long enough for an administrator to
            # reject/delete the draft or for ownership/publication state to
            # change. Re-read and lock the source row immediately before
            # creating document metadata so a stale decision cannot commit a
            # CV review under the old workflow state.
            current_crew = (
                await session.execute(
                    _select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
                )
            ).scalar_one_or_none()
            if current_crew is None:
                raise HTTPException(status_code=404, detail="Crew member not found")
            if not is_contractor_profile(current_crew):
                raise HTTPException(status_code=404, detail="Crew member not found")
            if current_user.role != "admin" and (
                current_crew.publication_status != "draft"
                or current_crew.submitted_by != current_user.id
            ):
                raise HTTPException(
                    status_code=403,
                    detail="This draft is no longer available for your upload",
                )
            draft_values = {
                "full_name": current_crew.full_name,
                "email": current_crew.email,
                "phone": current_crew.phone,
                "nationality": current_crew.nationality,
            }
            doc = DocumentModel(
                id=document_id,
                crew_member_id=crew_id,
                file_name=safe_file_name,
                file_type=file_type,
                file_size=file_size,
                storage_type=storage_type,
                storage_path=storage_path,
                dropbox_path=dropbox_path,
                classification=classification,
                title=clean_title,
                issue_date=parsed_issue_date,
                expiry_date=parsed_expiry_date,
                notes=clean_notes,
                extraction_status="pending",
                upload_key=idempotency_key,
                uploaded_by=getattr(current_user, "id", None)
                or getattr(current_user, "email", None),
            )
            session.add(doc)
            try:
                # Flush the parent row first: Document and CVReview are linked
                # by FK only (no ORM relationship), so a combined flush has no
                # guaranteed parent-first order. SQLite tolerates the inverted
                # order (FKs unenforced); PostgreSQL raises IntegrityError.
                # The flush also belongs in the recovery block because a
                # concurrent idempotent retry fails on the unique key here.
                await session.flush()
                if classification == "cv":
                    session.add(
                        CVReview(
                            document_id=document_id,
                            crew_member_id=crew_id,
                            submitted_by=current_user.id,
                            status="processing",
                            prior_publication_status=current_crew.publication_status,
                            proposed_data=draft_values,
                        )
                    )
                await session.commit()
            except IntegrityError:
                # Two retries can arrive at the same time. The unique index
                # makes one request the owner; the loser returns that same
                # record after rolling back instead of leaking a second file.
                await session.rollback()
                if not idempotency_key:
                    raise
                existing = (
                    await session.execute(
                        _select(DocumentModel).where(DocumentModel.upload_key == idempotency_key)
                    )
                ).scalar_one_or_none()
                if existing is None:
                    raise
                if existing.crew_member_id != crew_id or existing.uploaded_by == "agent":
                    raise HTTPException(status_code=409, detail="Upload key already used")
                await _cleanup_saved_upload(storage_type, storage_path)
                return {
                    "id": existing.id,
                    "file_name": existing.file_name,
                    "file_type": existing.file_type,
                    "file_size": existing.file_size,
                    "status": existing.extraction_status,
                    "storage_type": existing.storage_type,
                }

        dispatch_status = "pending"
        try:
            process_document_extraction.delay(document_id)
        except Exception:
            logger.warning("Could not queue document extraction task")
            dispatch_status = "failed"
            async with get_session_factory()() as session:
                doc = (
                    await session.execute(
                        _select(DocumentModel)
                        .where(DocumentModel.id == document_id)
                        .with_for_update()
                    )
                ).scalar_one()
                if doc.extraction_status == "pending":
                    doc.extraction_status = "failed"
                    if classification == "cv":
                        review = (
                            await session.execute(
                                _select(CVReview)
                                .where(CVReview.document_id == document_id)
                                .with_for_update()
                            )
                        ).scalar_one_or_none()
                        if review is not None and review.status == "processing":
                            review.status = "failed"
                    await session.commit()

        return {
            "id": document_id,
            "file_name": safe_file_name,
            "file_type": file_type,
            "file_size": file_size,
            "status": dispatch_status,
            "storage_type": storage_type,
        }
    except HTTPException:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        raise
    except DropboxStorageError as e:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        raise HTTPException(
            status_code=503, detail="Document storage is temporarily unavailable"
        ) from e
    except ValueError as e:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        raise HTTPException(status_code=400, detail="Invalid document upload") from e
    except Exception as e:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        logger.error("Document upload failed (%s)", type(e).__name__)
        raise HTTPException(status_code=500, detail="Upload failed")


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: CrewMember = Depends(require_admin_rest),
) -> StreamingResponse:
    """Download a document. T3 (admin/compliance) only — raw bytes are C3.

    Per docs/AUTHORIZATION.md and ADR 0005, compliance-only evidence (raw
    document bytes and extracted_text/data) is never available to T1/T2.
    """
    async with get_session_factory()() as session:
        from sqlalchemy import select

        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        # Retention of publication gate is defense-in-depth even for T3.
        if doc.crew_member_id:
            crew = (
                await session.execute(select(CrewMember).where(CrewMember.id == doc.crew_member_id))
            ).scalar_one_or_none()
            if (
                crew
                and (not is_contractor_profile(crew) or crew.publication_status != "approved")
                and crew.submitted_by != current_user.id
                and current_user.role != "admin"
            ):
                raise HTTPException(status_code=404, detail="Document not found")

        # Audit log: record access. C3 bytes must never leave without an audit
        # entry, so an audit-write failure fails the download (retryable 503)
        # instead of serving unlogged evidence.
        try:
            await audit_service.log_access(document_id, current_user.id, "download")
        except Exception as e:
            logger.warning("Document audit write failed (%s)", type(e).__name__)
            raise HTTPException(
                status_code=503, detail="Download audit unavailable; try again"
            ) from e

        # This route is async: use the async storage helper so a Dropbox
        # cache miss does not call asyncio.run() from inside the active loop.
        content = await document_upload_service.get_file_async(doc.storage_path)

        if content is None:
            raise HTTPException(status_code=404, detail="File not found on storage")
        valid, validation_error = document_upload_service.validate_file_content(
            doc.file_name, content
        )
        if not valid:
            logger.warning(
                "Refusing stored document download after content validation failure (%s)",
                validation_error,
            )
            raise HTTPException(status_code=422, detail="Stored document failed validation")

        return StreamingResponse(
            iter([content]),
            media_type="application/octet-stream",
            headers={"Content-Disposition": _content_disposition(doc.file_name)},
        )


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str, request: Request, current_user: CrewMember = Depends(require_staff_rest)
) -> dict[str, Any]:
    """Get document processing status. T2 (staff/admin) — C2 metadata only."""
    async with get_session_factory()() as session:
        from sqlalchemy import select

        # Match document -> contractor lock order used by revision, review,
        # and contractor-deletion workflows before detaching evidence.
        stmt = select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if not doc.crew_member_id and current_user.role != "admin":
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.crew_member_id and current_user.role != "admin":
            crew = (
                await session.execute(
                    select(CrewMember).where(CrewMember.id == doc.crew_member_id).with_for_update()
                )
            ).scalar_one_or_none()
            if crew is None or (
                not is_contractor_profile(crew)
                or (
                    crew.publication_status != "approved"
                    and not (
                        crew.publication_status == "draft" and crew.submitted_by == current_user.id
                    )
                )
            ):
                raise HTTPException(status_code=404, detail="Document not found")
        return {
            "id": doc.id,
            "file_name": doc.file_name,
            "extraction_status": doc.extraction_status,
            "classification": doc.classification,
            "storage_type": doc.storage_type,
        }


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    current_user: CrewMember = Depends(require_admin_rest),
) -> None:
    """Delete a document record and its managed file."""
    async with get_session_factory()() as session:
        from sqlalchemy import select

        # Match document -> contractor lock order used by revision, review,
        # and contractor-deletion workflows before detaching evidence.
        stmt = select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

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

        deleted_crew_id = doc.crew_member_id
        deleted_storage_path = doc.storage_path
        deleted_storage_type = doc.storage_type
        deleted_dropbox_path = doc.dropbox_path
        await session.delete(doc)
        await session.commit()
        cleanup_required = False
        # Commit the source-of-truth deletion before touching remote storage.
        # Deleting Dropbox first can leave a committed database row pointing at
        # a missing original if the metadata transaction then fails. A failed
        # remote cleanup is recoverable through the bounded orphan-cleanup task.
        if deleted_storage_type == "dropbox":
            remote_deleted = bool(
                deleted_dropbox_path
                and await document_upload_service.delete_from_dropbox(deleted_dropbox_path)
            )
            if not remote_deleted:
                cleanup_required = True
                logger.warning("Could not remove deleted document from Dropbox")
                from app.tasks.document_tasks import queue_orphaned_upload_cleanup

                queue_orphaned_upload_cleanup(
                    "dropbox", deleted_dropbox_path or deleted_storage_path
                )
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

        # The upload service restricts local deletion to its own cache path.
        # Remove it only after the metadata transaction succeeds; otherwise a
        # failed commit would leave a live document row without its file.
        try:
            document_upload_service.delete_file(deleted_storage_path)
        except Exception as exc:
            cleanup_required = True
            logger.warning("Could not remove deleted document cache (%s)", type(exc).__name__)
            from app.tasks.document_tasks import queue_local_document_cache_cleanup

            queue_local_document_cache_cleanup(deleted_storage_path)
        from app.config import get_settings
        from app.services.consultant_knowledge import consultant_knowledge_service

        try:
            if not await consultant_knowledge_service.reconcile_document_index(document_id):
                cleanup_required = True
                logger.warning("Deleted document search cleanup was not confirmed")
        except Exception as exc:
            cleanup_required = True
            logger.warning(
                "Could not remove deleted document search projection (%s)", type(exc).__name__
            )
        if get_settings().ENABLE_SEMANTIC_SEARCH:
            try:
                from app.services.qdrant import qdrant_service

                if not await qdrant_service.delete_document(document_id):
                    cleanup_required = True
                    logger.warning("Deleted document vector cleanup was not confirmed")
            except Exception as exc:
                cleanup_required = True
                logger.warning(
                    "Could not remove deleted document embedding (%s)", type(exc).__name__
                )
        if cleanup_required:
            from app.tasks.document_tasks import queue_document_projection_cleanup

            queue_document_projection_cleanup(document_id)


@router.post("/agent/upload")
async def agent_upload_document(
    request: Request,
    crew_id: str = Form(...),
    file: UploadFile = File(...),
    classification: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Form(None),
    api_key: bool = Depends(require_api_key),
) -> dict[str, Any]:
    """Upload a document for a crew member (agent access via API key)."""
    is_valid, error_msg = document_upload_service.validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    safe_file_name = file.filename or "upload"
    try:
        classification = (
            normalize_classification(classification) if classification is not None else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document category") from exc
    if classification == "cv":
        raise HTTPException(
            status_code=403,
            detail="CVs must use the staff upload and administrator review workflow",
        )
    if idempotency_key is not None and not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key):
        raise HTTPException(status_code=400, detail="Invalid upload idempotency key")

    async with get_session_factory()() as _crew_sess:
        crew_exists = (
            await _crew_sess.execute(
                select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
            )
        ).scalar_one_or_none()
        if (
            crew_exists is None
            or not is_contractor_profile(crew_exists)
            or crew_exists.publication_status == "rejected"
        ):
            raise HTTPException(status_code=404, detail="Crew member not found")
        if idempotency_key:
            existing = (
                await _crew_sess.execute(
                    select(DocumentModel).where(DocumentModel.upload_key == idempotency_key)
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.uploaded_by != "agent":
                    raise HTTPException(status_code=409, detail="Upload key already used")
                if existing.crew_member_id != crew_id:
                    raise HTTPException(status_code=409, detail="Upload key already used")
                retry_status = await _retry_failed_idempotent_document(_crew_sess, existing)
                return {
                    "id": existing.id,
                    "file_name": existing.file_name,
                    "file_type": existing.file_type,
                    "file_size": existing.file_size,
                    "status": retry_status,
                    "storage_type": existing.storage_type,
                }

    saved_storage_path: str | None = None
    saved_storage_type: str | None = None
    try:
        document_id, storage_path, file_size = await document_upload_service.save_file(
            file, crew_id, classification
        )
        file_type = document_upload_service.get_file_type(safe_file_name)

        storage_type = "dropbox" if storage_path.startswith("/hydenlyne/") else "local"
        dropbox_path = storage_path if storage_type == "dropbox" else None
        saved_storage_path = storage_path
        saved_storage_type = storage_type

        async with get_session_factory()() as session:
            current_crew = (
                await session.execute(
                    select(CrewMember).where(CrewMember.id == crew_id).with_for_update()
                )
            ).scalar_one_or_none()
            if (
                current_crew is None
                or not is_contractor_profile(current_crew)
                or current_crew.publication_status == "rejected"
            ):
                raise HTTPException(status_code=404, detail="Crew member not found")
            doc = DocumentModel(
                id=document_id,
                crew_member_id=crew_id,
                file_name=safe_file_name,
                file_type=file_type,
                file_size=file_size,
                storage_type=storage_type,
                storage_path=storage_path,
                dropbox_path=dropbox_path,
                classification=classification,
                extraction_status="pending",
                upload_key=idempotency_key,
                uploaded_by="agent",
            )
            session.add(doc)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                if not idempotency_key:
                    raise
                existing = (
                    await session.execute(
                        select(DocumentModel).where(DocumentModel.upload_key == idempotency_key)
                    )
                ).scalar_one_or_none()
                if existing is None:
                    raise
                if existing.crew_member_id != crew_id or existing.uploaded_by != "agent":
                    raise HTTPException(status_code=409, detail="Upload key already used")
                await _cleanup_saved_upload(storage_type, storage_path)
                return {
                    "id": existing.id,
                    "file_name": existing.file_name,
                    "file_type": existing.file_type,
                    "file_size": existing.file_size,
                    "status": existing.extraction_status,
                    "storage_type": existing.storage_type,
                }

        dispatch_status = "pending"
        try:
            process_document_extraction.delay(document_id)
        except Exception as e:
            logger.warning("Could not queue extraction task (%s)", type(e).__name__)
            dispatch_status = "failed"
            async with get_session_factory()() as session:
                queued_doc = (
                    await session.execute(
                        select(DocumentModel)
                        .where(DocumentModel.id == document_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if queued_doc is not None and queued_doc.extraction_status == "pending":
                    queued_doc.extraction_status = "failed"
                    if classification == "cv":
                        review = (
                            await session.execute(
                                select(CVReview)
                                .where(CVReview.document_id == document_id)
                                .with_for_update()
                            )
                        ).scalar_one_or_none()
                        if review is not None and review.status == "processing":
                            review.status = "failed"
                    await session.commit()

        return {
            "id": document_id,
            "file_name": safe_file_name,
            "file_type": file_type,
            "file_size": file_size,
            "status": dispatch_status,
            "storage_type": storage_type,
        }
    except HTTPException:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        raise
    except DropboxStorageError as e:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        raise HTTPException(
            status_code=503, detail="Document storage is temporarily unavailable"
        ) from e
    except ValueError as e:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        raise HTTPException(status_code=400, detail="Invalid document upload") from e
    except Exception as e:
        await _cleanup_saved_upload(saved_storage_type, saved_storage_path)
        logger.error("Agent upload failed (%s)", type(e).__name__)
        raise HTTPException(status_code=500, detail="Upload failed")
