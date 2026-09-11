from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select

from app.auth.decorators import require_admin_rest
from app.config import get_settings
from app.database import get_session_factory
from app.models import CrewMember
from app.models import Document as DocumentModel
from app.services.audit import audit_service
from app.services.cache import cache_service
from app.services.dropbox_auth import (
    DropboxAuthError,
    dropbox_request,
    token_provider,
)
from app.services.upload import document_upload_service
from app.tasks.document_tasks import process_dropbox_document

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dropbox", tags=["dropbox"])


@router.get("/webhook")
async def dropbox_webhook_challenge(request: Request) -> dict[str, str]:
    """Handle Dropbox webhook verification challenge."""
    challenge = request.query_params.get("challenge")
    if challenge:
        return {"challenge": challenge}
    raise HTTPException(status_code=400, detail="No challenge provided")


@router.post("/webhook")
async def dropbox_webhook_handler(
    request: Request, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Handle Dropbox webhook notifications for file changes."""
    raw_body = await request.body()
    signature = request.headers.get("X-Dropbox-Signature", "")
    # Enforce signature in production; in dev allow empty secret with warning
    if settings.APP_ENV == "production" and not settings.DROPBOX_APP_SECRET:
        raise HTTPException(status_code=503, detail="Dropbox webhook not configured")
    if settings.DROPBOX_APP_SECRET:
        expected = hmac.new(
            settings.DROPBOX_APP_SECRET.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=403, detail="Invalid signature")
    elif settings.APP_ENV == "production":
        raise HTTPException(status_code=403, detail="Missing signature")

    import json as _json

    try:
        body = _json.loads(raw_body.decode() or "{}")
    except _json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    logger.info("Dropbox webhook received")

    list_folder = body.get("list_folder", {})
    accounts = list_folder.get("accounts", [])

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
    except Exception as e:
        logger.error(f"Failed to process Dropbox account {account_id}: {e}")


async def get_dropbox_cursor(account_id: str) -> Optional[str]:
    """Get the stored cursor for an account (Redis-backed)."""
    try:
        key = f"dropbox:cursor:{account_id}"
        redis = await cache_service._get_redis()
        value = await redis.get(key)
        return value if isinstance(value, str) else None
    except Exception:
        return None


async def start_dropbox_listing(account_id: str) -> None:
    """Start listing files from Dropbox root."""
    if not token_provider.configured:
        logger.warning("Dropbox is not configured, skipping listing")
        return
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await dropbox_request(
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
        if response.status_code == 200:
            data = response.json()
            await process_dropbox_entries(data.get("entries", []))
            await save_dropbox_cursor(account_id, data.get("cursor"))
            # Handle pagination
            while data.get("has_more"):
                cursor = data.get("cursor")
                if not cursor:
                    break
                response = await dropbox_request(
                    client,
                    "POST",
                    "https://api.dropboxapi.com/2/files/list_folder/continue",
                    headers={"Content-Type": "application/json"},
                    json={"cursor": cursor},
                )
                if response.status_code != 200:
                    break
                data = response.json()
                await process_dropbox_entries(data.get("entries", []))
                await save_dropbox_cursor(account_id, data.get("cursor"))
        else:
            logger.error(
                "Dropbox list_folder failed %s: %s", response.status_code, response.text[:500]
            )


async def continue_dropbox_listing(account_id: str, cursor: str) -> None:
    """Continue listing files from a cursor."""
    if not token_provider.configured:
        return
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await dropbox_request(
            client,
            "POST",
            "https://api.dropboxapi.com/2/files/list_folder/continue",
            headers={"Content-Type": "application/json"},
            json={"cursor": cursor},
        )
        if response.status_code == 200:
            data = response.json()
            await process_dropbox_entries(data.get("entries", []))
            await save_dropbox_cursor(account_id, data.get("cursor"))
            while data.get("has_more"):
                cursor = data.get("cursor")
                if not cursor:
                    break
                response = await dropbox_request(
                    client,
                    "POST",
                    "https://api.dropboxapi.com/2/files/list_folder/continue",
                    headers={"Content-Type": "application/json"},
                    json={"cursor": cursor},
                )
                if response.status_code != 200:
                    break
                data = response.json()
                await process_dropbox_entries(data.get("entries", []))
                await save_dropbox_cursor(account_id, data.get("cursor"))


async def process_dropbox_entries(entries: list[dict]) -> None:
    """Process Dropbox file entries."""
    for entry in entries:
        if entry.get(".tag") == "file":
            await process_dropbox_file(entry)
        elif entry.get(".tag") == "deleted":
            await process_dropbox_deletion(entry.get("path_lower", ""))


async def process_dropbox_deletion(file_path: str) -> None:
    """Remove a record for content deleted outside the application."""
    if not file_path:
        return
    async with get_session_factory()() as session:
        result = await session.execute(
            select(DocumentModel).where(DocumentModel.dropbox_path == file_path)
        )
        doc = result.scalar_one_or_none()
        if doc:
            document_upload_service.delete_file(doc.storage_path)
            await session.delete(doc)
            await session.commit()


async def process_dropbox_file(file_entry: dict) -> None:
    """Process a single Dropbox file."""
    file_path = file_entry.get("path_lower", "")
    file_name = file_entry.get("name", "")

    allowed_extensions = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".eml", ".msg"}
    if not any(file_name.lower().endswith(ext) for ext in allowed_extensions):
        return

    async with get_session_factory()() as session:
        existing = await session.execute(
            select(DocumentModel).where(DocumentModel.dropbox_path == file_path)
        )
        doc = existing.scalar_one_or_none()
        if doc:
            # Dropbox sends a new revision for a modified file.  Requeue it
            # rather than silently serving stale extracted metadata.
            if doc.dropbox_revision != file_entry.get("rev"):
                doc.dropbox_revision = file_entry.get("rev")
                doc.file_size = file_entry.get("size", doc.file_size)
                doc.extraction_status = "pending"
                await session.commit()
                process_dropbox_document.delay(doc.id)
            return

        # App-managed files live at /hydenlyne/<crew_id>/documents/... —
        # recover the owner so the row joins the staff review queue instead
        # of becoming a crew-less orphan visible only to admins.
        crew_member_id: Optional[str] = None
        parts = file_path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "hydenlyne":
            candidate = parts[1]
            owner = await session.execute(select(CrewMember).where(CrewMember.id == candidate))
            if owner.scalar_one_or_none() is not None:
                crew_member_id = candidate

        doc = DocumentModel(
            file_name=file_name,
            file_type=file_name.split(".")[-1].lower(),
            file_size=file_entry.get("size", 0),
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

        process_dropbox_document.delay(doc.id)
        logger.info("New managed Dropbox document queued")


async def save_dropbox_cursor(account_id: str, cursor: Optional[str]) -> None:
    """Save the cursor for an account (Redis)."""
    if not cursor:
        return
    try:
        key = f"dropbox:cursor:{account_id}"
        redis = await cache_service._get_redis()
        await redis.set(key, cursor)
    except Exception as e:
        logger.warning(f"Failed to save dropbox cursor: {e}")


@router.post("/download/{document_id}")
async def download_dropbox_file(
    document_id: str,
    request: Request,
    current_user: CrewMember = Depends(require_admin_rest),
) -> dict[str, Any]:
    """Download a file from Dropbox by document ID. T3 (admin) only — C3 bytes."""
    async with get_session_factory()() as session:
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc or doc.storage_type != "dropbox":
            raise HTTPException(status_code=404, detail="Document not found")

        # Audit log: record access
        try:
            await audit_service.log_access(document_id, current_user.id, "download")
        except Exception as e:
            logger.warning(f"Audit log failed for dropbox download: {e}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await dropbox_request(
                    client,
                    "POST",
                    "https://content.dropboxapi.com/2/files/download",
                    headers={"Dropbox-API-Arg": json.dumps({"path": doc.dropbox_path})},
                )
            except DropboxAuthError as exc:
                logger.error("Dropbox auth unavailable for download: %s", exc)
                raise HTTPException(status_code=503, detail="Dropbox storage is unavailable")
            if response.status_code == 200:
                return {"status": "downloaded", "size": len(response.content)}
            raise HTTPException(status_code=response.status_code, detail="Download failed")
