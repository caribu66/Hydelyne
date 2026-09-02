from __future__ import annotations

import logging
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.auth.decorators import get_current_user_rest, require_admin_rest, require_api_key
from app.database import get_session_factory
from app.models import Document as DocumentModel
from app.services.audit import audit_service
from app.services.upload import DropboxStorageError, document_upload_service
from app.tasks.document_tasks import process_document_extraction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/preview-cv")
async def preview_cv(
    file: UploadFile = File(...),
    current_user=Depends(require_admin_rest),
):
    """Extract CV identity fields before a crew record is created.

    This is intentionally a preview only: it never stores the uploaded bytes
    or creates database metadata. The subsequent document upload remains the
    single operation that writes the approved CV to Dropbox.
    """
    content = await file.read(50 * 1024 * 1024 + 1)
    is_valid, error_msg = document_upload_service.validate_file(file, content)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds maximum size of 52428800 bytes")

    suffix = Path(file.filename or "cv.pdf").suffix.lower()
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        from app.services.extraction import extraction_service
        from app.services.text_extraction import text_extraction_service

        file_type = document_upload_service.get_file_type(file.filename or "cv.pdf")
        cv_text = await asyncio.to_thread(
            text_extraction_service.extract_text_sync, temp_path, file_type
        )
        extracted = await asyncio.to_thread(
            extraction_service.extract_document_sync, cv_text, "cv"
        )
        return {
            "full_name": extracted.get("full_name"),
            "email": extracted.get("email"),
            "phone": extracted.get("phone"),
            "nationality": extracted.get("nationality"),
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
    current_user=Depends(require_admin_rest),
):
    """Upload a document for a crew member."""
    is_valid, error_msg = document_upload_service.validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Validate crew exists if crew_id looks like UUID (avoid FK orphan)
    try:
        from sqlalchemy import select as _select

        from app.models import CrewMember as _CrewModel

        async with get_session_factory()() as _sess:
            _cs = await _sess.execute(_select(_CrewModel).where(_CrewModel.id == crew_id))
            if not _cs.scalar_one_or_none():
                # For local dev allow orphan but warn; in prod strictly require crew
                from app.config import get_settings as _gs_docs

                if _gs_docs().APP_ENV == "production":
                    raise HTTPException(status_code=404, detail="Crew member not found")
                logger.warning(f"Upload for unknown crew_id {crew_id} — allowed in non-prod")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Crew existence check skipped: {e}")

    try:
        document_id, storage_path, file_size = await document_upload_service.save_file(
            file, crew_id, classification
        )
        file_type = document_upload_service.get_file_type(file.filename)

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
                uploaded_by=getattr(current_user, "id", None) or getattr(current_user, "email", None),
            )
            session.add(doc)
            await session.commit()

        try:
            process_document_extraction.delay(document_id)
        except Exception as e:
            logger.warning(f"Could not queue extraction task: {e}")

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
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user=Depends(get_current_user_rest),
):
    """Download a document."""
    async with get_session_factory()() as session:
        from sqlalchemy import select

        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Audit log: record access
        try:
            await audit_service.log_access(document_id, current_user.id, "download")
        except Exception as e:
            logger.warning(f"Audit log failed for download: {e}")

        # Try local cache first, then Dropbox
        content = document_upload_service.get_file(doc.storage_path)

        if content is None and doc.storage_type == "dropbox" and doc.dropbox_path:
            content = await document_upload_service.download_from_dropbox(doc.dropbox_path)

        if content is None:
            raise HTTPException(status_code=404, detail="File not found on storage")

        return StreamingResponse(
            iter([content]),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{doc.file_name}"'},
        )


@router.get("/{document_id}/status")
async def get_document_status(document_id: str, request: Request, current_user=Depends(get_current_user_rest)):
    """Get document processing status."""
    async with get_session_factory()() as session:
        from sqlalchemy import select

        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
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
    current_user=Depends(require_admin_rest),
):
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
            if not doc.dropbox_path or not await document_upload_service.delete_from_dropbox(doc.dropbox_path):
                raise HTTPException(status_code=502, detail="Dropbox deletion failed; document was retained")

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
    api_key=Depends(require_api_key),
):
    """Upload a document for a crew member (agent access via API key)."""
    is_valid, error_msg = document_upload_service.validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        document_id, storage_path, file_size = await document_upload_service.save_file(
            file, crew_id, classification
        )
        file_type = document_upload_service.get_file_type(file.filename)

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
                uploaded_by="agent",
            )
            session.add(doc)
            await session.commit()

        try:
            process_document_extraction.delay(document_id)
        except Exception as e:
            logger.warning(f"Could not queue extraction task: {e}")

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
        logger.error(f"Agent upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")
