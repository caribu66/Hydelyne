from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from datetime import timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.decorators import (
    require_admin_rest,
    require_api_key,
    require_staff_rest,
)
from app.database import get_session_factory
from app.domain.fields import normalize_classification
from app.models import CrewMember, CVReview, IncomingDocumentReview
from app.models import Document as DocumentModel
from app.services.audit import audit_service
from app.services.document_requests import document_request_service
from app.services.upload import DropboxStorageError, document_upload_service, safe_path_component
from app.tasks.document_tasks import process_document_extraction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _content_disposition(filename: str | None) -> str:
    """Build a header-safe Content-Disposition value (RFC 6266/5987).

    Stored file names are raw client input: quotes, semicolons, or newlines
    would break out of `filename="..."`. Emit a sanitized ASCII fallback
    plus the RFC 5987 `filename*` UTF-8 form.
    """
    from urllib.parse import quote

    original = filename or "download"
    safe = re.sub(r"[^\w.\- ]", "_", original).strip()[:100] or "download"
    return f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(original)}"


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
        existing = (
            await session.execute(
                _select(DocumentModel).where(DocumentModel.upload_key == upload_key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {
                "id": existing.id,
                "file_name": existing.file_name,
                "status": existing.extraction_status,
            }

    try:
        document_id, storage_path, file_size = await document_upload_service.save_file(
            file, request.crew_member_id, classification
        )
        file_type = document_upload_service.get_file_type(file.filename or "upload")
        storage_type = "dropbox" if storage_path.startswith("/hydenlyne/") else "local"
        async with get_session_factory()() as session:
            doc = DocumentModel(
                id=document_id,
                crew_member_id=request.crew_member_id,
                file_name=file.filename or "upload",
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
            session.add(IncomingDocumentReview(request_id=request.id, document_id=document_id))
            try:
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
                if storage_type == "dropbox" and storage_path.startswith("/hydenlyne/"):
                    await document_upload_service.delete_from_dropbox(storage_path)
                else:
                    document_upload_service.delete_file(storage_path)
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
                        _select(DocumentModel).where(DocumentModel.id == document_id)
                    )
                ).scalar_one()
                doc.extraction_status = "failed"
                await session.commit()
        return {
            "id": document_id,
            "file_name": file.filename or "upload",
            "status": dispatch_status,
        }
    except DropboxStorageError as exc:
        raise HTTPException(
            status_code=503, detail="Document storage is temporarily unavailable"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
            .where(IncomingDocumentReview.status.in_(["unread", "claimed"]))
        )
        if current_user.role != "admin":
            from sqlalchemy import or_

            query = query.where(
                or_(
                    CrewMember.publication_status == "approved",
                    CrewMember.submitted_by == current_user.id,
                )
            )
        rows = await session.execute(
            query.order_by(IncomingDocumentReview.created_at.desc()).limit(100)
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
    content = await file.read(50 * 1024 * 1024 + 1)
    is_valid, error_msg = document_upload_service.validate_file(file, content)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds maximum size of 52428800 bytes")

    empty_result = {"full_name": None, "email": None, "phone": None, "nationality": None}

    suffix = Path(file.filename or "cv.pdf").suffix.lower()
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

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
    except Exception:
        logger.exception("CV preview extraction failed")
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
    current_user: CrewMember = Depends(require_staff_rest),
) -> dict[str, Any]:
    """Upload a document for a crew member."""
    is_valid, error_msg = document_upload_service.validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    # Normalize once so storage, CV gating, and downstream filters agree.
    classification = normalize_classification(classification)
    try:
        crew_id = safe_path_component(crew_id, "crew_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if idempotency_key is not None and not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key):
        raise HTTPException(status_code=400, detail="Invalid upload idempotency key")

    from sqlalchemy import select as _select

    async with get_session_factory()() as _sess:
        crew = (
            await _sess.execute(_select(CrewMember).where(CrewMember.id == crew_id))
        ).scalar_one_or_none()
        if crew is None:
            raise HTTPException(status_code=404, detail="Crew member not found")
        if current_user.role != "admin" and crew.submitted_by != current_user.id:
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
                if existing.crew_member_id != crew_id:
                    raise HTTPException(status_code=409, detail="Upload key already used")
                return {
                    "id": existing.id,
                    "file_name": existing.file_name,
                    "file_type": existing.file_type,
                    "file_size": existing.file_size,
                    "status": existing.extraction_status,
                    "storage_type": existing.storage_type,
                }

    try:
        document_id, storage_path, file_size = await document_upload_service.save_file(
            file, crew_id, classification
        )
        file_type = document_upload_service.get_file_type(file.filename or "upload")

        # Determine storage type based on path
        storage_type = "dropbox" if storage_path.startswith("/hydenlyne/") else "local"
        dropbox_path = storage_path if storage_type == "dropbox" else None

        async with get_session_factory()() as session:
            doc = DocumentModel(
                id=document_id,
                crew_member_id=crew_id,
                file_name=file.filename,
                file_type=file_type,
                file_size=file_size,
                storage_type=storage_type,
                storage_path=storage_path,
                dropbox_path=dropbox_path,
                classification=classification,
                extraction_status="pending",
                upload_key=idempotency_key,
                uploaded_by=getattr(current_user, "id", None)
                or getattr(current_user, "email", None),
            )
            session.add(doc)
            if classification == "cv":
                session.add(
                    CVReview(
                        document_id=document_id,
                        crew_member_id=crew_id,
                        submitted_by=current_user.id,
                        status="processing",
                        prior_publication_status=crew.publication_status,
                        proposed_data=draft_values,
                    )
                )
            try:
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
                if existing is None or existing.crew_member_id != crew_id:
                    raise
                if storage_type == "dropbox" and dropbox_path:
                    await document_upload_service.delete_from_dropbox(dropbox_path)
                else:
                    document_upload_service.delete_file(storage_path)
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
                        _select(DocumentModel).where(DocumentModel.id == document_id)
                    )
                ).scalar_one()
                doc.extraction_status = "failed"
                if classification == "cv":
                    review = (
                        await session.execute(
                            _select(CVReview).where(CVReview.document_id == document_id)
                        )
                    ).scalar_one()
                    review.status = "failed"
                await session.commit()

        return {
            "id": document_id,
            "file_name": file.filename,
            "file_type": file_type,
            "file_size": file_size,
            "status": dispatch_status,
            "storage_type": storage_type,
        }
    except DropboxStorageError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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
                and crew.publication_status != "approved"
                and crew.submitted_by != current_user.id
                and current_user.role != "admin"
            ):
                raise HTTPException(status_code=404, detail="Document not found")

        # Audit log: record access
        try:
            await audit_service.log_access(document_id, current_user.id, "download")
        except Exception as e:
            logger.warning("Document audit write failed (%s)", type(e).__name__)

        # Try local cache first, then Dropbox
        content = document_upload_service.get_file(doc.storage_path)

        if content is None and doc.storage_type == "dropbox" and doc.dropbox_path:
            content = await document_upload_service.download_from_dropbox(doc.dropbox_path)

        if content is None:
            raise HTTPException(status_code=404, detail="File not found on storage")

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

        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.crew_member_id and current_user.role != "admin":
            crew = (
                await session.execute(select(CrewMember).where(CrewMember.id == doc.crew_member_id))
            ).scalar_one_or_none()
            if (
                crew
                and crew.publication_status != "approved"
                and crew.submitted_by != current_user.id
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

        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Do not leave a recoverable Dropbox original behind when its database
        # record is removed.  Keep the record if remote deletion fails.
        if doc.storage_type == "dropbox":
            if not doc.dropbox_path or not await document_upload_service.delete_from_dropbox(
                doc.dropbox_path
            ):
                raise HTTPException(
                    status_code=502, detail="Dropbox deletion failed; document was retained"
                )

        # The upload service restricts local deletion to its own cache path.
        document_upload_service.delete_file(doc.storage_path)
        await session.delete(doc)
        await session.commit()


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
    classification = normalize_classification(classification)
    if classification == "cv":
        raise HTTPException(
            status_code=403,
            detail="CVs must use the staff upload and administrator review workflow",
        )
    if idempotency_key is not None and not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key):
        raise HTTPException(status_code=400, detail="Invalid upload idempotency key")

    async with get_session_factory()() as _crew_sess:
        crew_exists = (
            await _crew_sess.execute(select(CrewMember).where(CrewMember.id == crew_id))
        ).scalar_one_or_none()
        if crew_exists is None:
            raise HTTPException(status_code=404, detail="Crew member not found")
        if idempotency_key:
            existing = (
                await _crew_sess.execute(
                    select(DocumentModel).where(DocumentModel.upload_key == idempotency_key)
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.crew_member_id != crew_id:
                    raise HTTPException(status_code=409, detail="Upload key already used")
                return {
                    "id": existing.id,
                    "file_name": existing.file_name,
                    "file_type": existing.file_type,
                    "file_size": existing.file_size,
                    "status": existing.extraction_status,
                    "storage_type": existing.storage_type,
                }

    try:
        document_id, storage_path, file_size = await document_upload_service.save_file(
            file, crew_id, classification
        )
        file_type = document_upload_service.get_file_type(file.filename or "upload")

        storage_type = "dropbox" if storage_path.startswith("/hydenlyne/") else "local"
        dropbox_path = storage_path if storage_type == "dropbox" else None

        async with get_session_factory()() as session:
            doc = DocumentModel(
                id=document_id,
                crew_member_id=crew_id,
                file_name=file.filename,
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
            await session.commit()

        try:
            process_document_extraction.delay(document_id)
        except Exception as e:
            logger.warning("Could not queue extraction task (%s)", type(e).__name__)

        return {
            "id": document_id,
            "file_name": file.filename,
            "file_type": file_type,
            "file_size": file_size,
            "status": "pending",
            "storage_type": storage_type,
        }
    except DropboxStorageError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Agent upload failed (%s)", type(e).__name__)
        raise HTTPException(status_code=500, detail="Upload failed")
