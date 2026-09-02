from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.database import get_session_factory
from app.models import Document as DocumentModel

logger = logging.getLogger(__name__)


class AuditService:
    """Service for tracking document access and changes."""

    async def log_access(
        self,
        document_id: str,
        user_id: str,
        action: str,
        details: Optional[dict] = None,
        data_keys: Optional[list[str]] = None,
    ) -> None:
        """Log an access event for a document.

        Args:
            document_id: UUID of the document.
            user_id: ID of the user accessing the document.
            action: Type of access (view, download, edit, delete).
            details: Additional details about the access.
            data_keys: Optional list of keys touched (back-compat with callers using list).
        """
        async with get_session_factory()() as session:
            from sqlalchemy import select

            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return

            merged_details = details or {}
            if data_keys is not None:
                merged_details = {**merged_details, "data_keys": data_keys}
            access_entry = {
                "user_id": user_id,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": merged_details,
            }

            access_log = doc.access_log or []
            access_log.append(access_entry)
            doc.access_log = access_log
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(doc, "access_log")

            await session.commit()
            logger.info(f"Logged {action} on document {document_id} by user {user_id}")

    async def log_extraction(
        self,
        document_id: str,
        model_used: str,
        confidence: dict,
        status: str,
    ) -> None:
        """Log an extraction event.

        Args:
            document_id: UUID of the document.
            model_used: Name of the model used for extraction.
            confidence: Confidence scores for extracted fields.
            status: Status of the extraction (extracted, failed, needs_review).
        """
        async with get_session_factory()() as session:
            from sqlalchemy import select

            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return

            extraction_entry = {
                "event": "extraction",
                "model": model_used,
                "confidence": confidence,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            access_log = doc.access_log or []
            access_log.append(extraction_entry)
            doc.access_log = access_log
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(doc, "access_log")

            await session.commit()

    async def get_document_history(self, document_id: str) -> list[dict]:
        """Get the full history of a document.

        Args:
            document_id: UUID of the document.

        Returns:
            List of history entries.
        """
        async with get_session_factory()() as session:
            from sqlalchemy import select

            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                return []

            return doc.access_log or []


audit_service = AuditService()
