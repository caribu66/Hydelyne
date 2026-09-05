from __future__ import annotations

import json as json_module
import logging
import re
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Optional

import httpx
from fastapi import UploadFile

from app.config import get_settings
from app.services.dropbox_auth import dropbox_request, token_provider

settings = get_settings()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".eml", ".msg"}
MAX_FILE_SIZE = 50 * 1024 * 1024
CHUNK_SIZE = 8192

SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_PATH_COMPONENT_LEN = 255

MAGIC_SIGNATURES = {
    ".pdf": [b"%PDF"],
    ".docx": [b"PK\x03\x04"],
    ".doc": [b"\xd0\xcf\x11\xe0"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".eml": [b"From "],
    ".msg": [b"\xd0\xcf\x11\xe0"],
}


class DropboxStorageError(RuntimeError):
    """Raised when Dropbox is the required source of record but is unavailable."""


def safe_path_component(value: str, label: str = "path_component") -> str:
    """Validate a single path component to prevent directory traversal.

    Rejects values containing path separators, ``..``, or characters outside
    ``[A-Za-z0-9._-]``.  Length-capped to ``MAX_PATH_COMPONENT_LEN``.
    Raises ``ValueError`` on invalid input.
    """
    if not value or not isinstance(value, str):
        raise ValueError(f"Invalid {label}: must be a non-empty string")
    if not SAFE_PATH_RE.match(value):
        raise ValueError(f"Invalid {label}: contains forbidden characters")
    if ".." in value:
        raise ValueError(f"Invalid {label}: traversal sequence not allowed")
    if len(value) > MAX_PATH_COMPONENT_LEN:
        raise ValueError(f"Invalid {label}: too long")
    return value


def storage_filename(value: str) -> str:
    """Return a safe storage key while preserving the display filename.

    CVs routinely contain spaces and Unicode characters.  The database keeps
    the original filename for users, while storage keys are normalised so they
    remain valid local and Dropbox path components.
    """
    filename = Path(value).name
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    if not normalized:
        raise ValueError("Invalid filename")
    return safe_path_component(normalized, "filename")


def _validate_magic_bytes(ext: str, magic: bytes) -> bool:
    """Return True if *magic* matches the expected signature for *ext*."""
    expected = MAGIC_SIGNATURES.get(ext)
    if not expected:
        return True
    return any(magic.startswith(sig) for sig in expected)


class DocumentUploadService:
    """Service for handling document uploads to Dropbox with local caching."""

    def __init__(self) -> None:
        self.storage_path = Path(settings.DOCUMENT_STORAGE_PATH)
        self.cache_path = self.storage_path / ".cache"
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self.cache_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.storage_path = Path("./data/documents")
            self.cache_path = self.storage_path / ".cache"
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self.cache_path.mkdir(parents=True, exist_ok=True)
        self.dropbox_available = token_provider.configured

    def validate_file(
        self, file: UploadFile, file_content: Optional[bytes] = None
    ) -> tuple[bool, str]:
        """Validate file type (extension + optional magic bytes).

        If *file_content* is provided, its first 16 bytes are checked against
        known file signatures.  When *file_content* is None (the common case
        in async request handlers), only the extension is checked here;
        :meth:`save_file` performs the full magic-byte check on the streamed
        temp file.
        """
        if not file.filename:
            return False, "No filename provided"

        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"File type {ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

        if file_content is not None:
            magic = file_content[:16]
            if magic and not _validate_magic_bytes(ext, magic):
                return False, f"File content does not match extension {ext}"

        return True, ""

    async def save_file(
        self,
        file: UploadFile,
        crew_id: str,
        classification: Optional[str] = None,
    ) -> tuple[str, str, int]:
        """Save uploaded file to Dropbox with local caching.

        Streams the upload in ``CHUNK_SIZE`` chunks to a temp file, enforces
        ``MAX_FILE_SIZE`` *before* any DB write, validates magic bytes, and
        sanitises ``crew_id`` / ``classification`` to prevent path traversal.

        Returns:
            Tuple of (document_id, storage_path, file_size)

        Raises:
            ValueError: if ``file.filename`` is empty. Callers are expected to
                have already run ``validate_file``, but this method must not
                trust that and crash confusingly on a missing filename.
        """
        if not file.filename:
            raise ValueError("No filename provided")
        safe_crew_id = safe_path_component(crew_id, "crew_id")
        safe_classification = (
            safe_path_component(classification, "classification") if classification else None
        )
        document_id = str(uuid.uuid4())
        safe_filename = storage_filename(file.filename)

        # Stream to a temp file, enforcing size limit before any DB write
        total_size = 0
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    tmp.close()
                    tmp_path.unlink(missing_ok=True)
                    raise ValueError(f"File exceeds maximum size of {MAX_FILE_SIZE} bytes")
                tmp.write(chunk)

        # Read header for magic-byte validation
        with open(tmp_path, "rb") as f:
            header = f.read(16)
        ext = Path(file.filename).suffix.lower()
        if not _validate_magic_bytes(ext, header):
            tmp_path.unlink(missing_ok=True)
            raise ValueError(f"File content does not match extension {ext}")

        try:
            file_content = tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

        # Save to local cache
        crew_cache_dir = self.cache_path / safe_crew_id
        crew_cache_dir.mkdir(parents=True, exist_ok=True)
        local_cache_path = crew_cache_dir / f"{document_id}_{safe_filename}"
        local_cache_path.write_bytes(file_content)

        # Upload to Dropbox if available
        dropbox_path = None
        if self.dropbox_available:
            dropbox_path = await self._upload_to_dropbox(
                file_content, safe_crew_id, safe_filename, document_id, safe_classification
            )

        if settings.REQUIRE_DROPBOX_STORAGE and not dropbox_path:
            # Do not leave an untracked local-only file when Dropbox is the
            # required system of record.  The database write has not happened
            # yet, so removing this just-created cache copy is safe.
            local_cache_path.unlink(missing_ok=True)
            raise DropboxStorageError(
                "Dropbox storage is required, but the file could not be uploaded"
            )

        storage_path = dropbox_path or str(local_cache_path)

        logger.info(
            f"Saved file {safe_filename} for crew {safe_crew_id} "
            f"(dropbox={'yes' if dropbox_path else 'no'}, cache=yes)"
        )
        return document_id, storage_path, total_size

    async def _upload_to_dropbox(
        self,
        file_content: bytes,
        crew_id: str,
        filename: str,
        document_id: str,
        classification: Optional[str] = None,
    ) -> Optional[str]:
        """Upload file to Dropbox. Returns Dropbox path or None on failure."""
        safe_crew_id = safe_path_component(crew_id, "crew_id")
        safe_filename = safe_path_component(filename, "filename")
        folder = (
            safe_path_component(classification, "classification")
            if classification
            else "uncategorized"
        )
        dropbox_path = f"/hydenlyne/{safe_crew_id}/documents/{folder}/{document_id}_{safe_filename}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await dropbox_request(
                    client,
                    "POST",
                    "https://content.dropboxapi.com/2/files/upload",
                    headers={
                        "Content-Type": "application/octet-stream",
                        "Dropbox-API-Arg": json_module.dumps(
                            {
                                "path": dropbox_path,
                                "mode": "add",
                                "autorename": True,
                                "mute": False,
                            }
                        ),
                    },
                    content=file_content,
                    timeout=60.0,
                )

                if response.status_code == 200:
                    logger.info("Uploaded managed document to Dropbox")
                    return dropbox_path
                else:
                    logger.warning("Dropbox upload failed with status %s", response.status_code)
        except Exception as e:
            logger.warning("Dropbox upload error (%s)", type(e).__name__)

        return None

    def get_file(self, storage_path: str) -> Optional[bytes]:
        """Read file from local cache or Dropbox.

        ``storage_path`` is treated as untrusted; only paths that resolve
        inside ``self.cache_path`` or are valid Dropbox paths (``/hydenlyne/…``)
        are honoured.  The raw local-path fallback is removed to prevent
        arbitrary file read.
        """
        # Check local cache first
        local_path = self._get_local_cache_path(storage_path)
        if local_path and local_path.exists():
            # Resolve and verify the path stays within cache_path
            resolved = local_path.resolve()
            if not str(resolved).startswith(str(self.cache_path.resolve())):
                logger.warning("Refusing out-of-cache document read")
                return None
            return local_path.read_bytes()

        # Try to download from Dropbox and cache locally
        if self.dropbox_available and storage_path.startswith("/hydenlyne/"):
            content = self._download_from_dropbox_sync(storage_path)
            if content:
                if local_path:
                    resolved = local_path.resolve()
                    if str(resolved).startswith(str(self.cache_path.resolve())):
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        local_path.write_bytes(content)
                return content

        return None

    def stream_file(self, storage_path: str) -> Optional[Iterator[bytes]]:
        """Stream file content in chunks."""
        content = self.get_file(storage_path)
        if content is None:
            return None

        def file_iterator() -> Iterator[bytes]:
            for i in range(0, len(content), CHUNK_SIZE):
                yield content[i : i + CHUNK_SIZE]

        return file_iterator()

    def delete_file(self, storage_path: str) -> bool:
        """Delete file from local cache."""
        local_path = self._get_local_cache_path(storage_path)
        if local_path and local_path.exists():
            local_path.unlink()
            return True
        return False

    async def delete_from_dropbox(self, dropbox_path: str) -> bool:
        """Delete a managed Dropbox object.

        A database record must not be removed while its Dropbox source remains.
        Callers should stop the deletion if this returns ``False`` so the
        record continues to point at recoverable content.
        """
        if not self.dropbox_available or not dropbox_path.startswith("/hydenlyne/"):
            return False

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await dropbox_request(
                    client,
                    "POST",
                    "https://api.dropboxapi.com/2/files/delete_v2",
                    headers={"Content-Type": "application/json"},
                    json={"path": dropbox_path},
                    timeout=60.0,
                )
                if response.status_code == 200:
                    return True
                logger.warning(
                    "Dropbox delete failed (%s): %s",
                    response.status_code,
                    response.text[:200],
                )
        except Exception as e:
            logger.warning("Dropbox delete error: %s", e)
        return False

    def _get_local_cache_path(self, storage_path: str) -> Optional[Path]:
        """Get local cache path for a storage path.

        Dropbox path: /hydenlyne/{crew_id}/documents/{folder}/{document_id}_{filename}
        Local path:   {cache_path}/{crew_id}/{document_id}_{filename}
        """
        parts = [part for part in storage_path.split("/") if part]
        if storage_path.startswith("/hydenlyne/"):
            # /hydenlyne/{crew_id}/documents/{classification}/{file}
            if len(parts) == 5 and parts[0] == "hydenlyne" and parts[2] == "documents":
                candidate_crew, candidate_file = parts[1], parts[4]
            elif len(parts) >= 4:
                # Preserve cache access for pre-structured Dropbox paths.
                candidate_crew, candidate_file = parts[-2], parts[-1]
            else:
                return None
        else:
            # Local records are written as .../.cache/{crew_id}/{file}.
            try:
                cache_index = parts.index(".cache")
                candidate_crew, candidate_file = parts[cache_index + 1], parts[cache_index + 2]
            except (ValueError, IndexError):
                return None
        try:
            crew_id = safe_path_component(candidate_crew, "crew_id")
            filename = safe_path_component(candidate_file, "filename")
        except ValueError:
            return None
        return self.cache_path / crew_id / filename

    def _download_from_dropbox_sync(self, dropbox_path: str) -> Optional[bytes]:
        """Synchronous Dropbox download (for use in sync context)."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # We're in an async context, can't use run_until_complete
            # Return None and let the caller handle async download
            logger.debug("Cannot sync download in async context, skipping")
            return None

        return loop.run_until_complete(self._download_from_dropbox(dropbox_path))

    async def download_from_dropbox(self, dropbox_path: str) -> Optional[bytes]:
        """Async Dropbox download with caching."""
        return await self._download_from_dropbox(dropbox_path)

    async def _download_from_dropbox(self, dropbox_path: str) -> Optional[bytes]:
        """Download file from Dropbox and cache locally."""
        if not self.dropbox_available:
            return None

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await dropbox_request(
                    client,
                    "POST",
                    "https://content.dropboxapi.com/2/files/download",
                    headers={"Dropbox-API-Arg": json_module.dumps({"path": dropbox_path})},
                    timeout=60.0,
                )

                if response.status_code == 200:
                    content = response.content
                    # Cache locally
                    local_path = self._get_local_cache_path(dropbox_path)
                    if local_path:
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        local_path.write_bytes(content)
                    return content
                else:
                    logger.warning(
                        f"Dropbox download failed ({response.status_code}): {response.text[:200]}"
                    )
        except Exception as e:
            logger.warning("Dropbox download error (%s)", type(e).__name__)

        return None

    def get_file_type(self, file_name: str) -> str:
        """Get file extension."""
        return Path(file_name).suffix.lower().lstrip(".")


document_upload_service = DocumentUploadService()
