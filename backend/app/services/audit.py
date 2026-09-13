from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Optional

from app.database import get_session_factory
from app.models import Document as DocumentModel
from app.models import ProfileAccessEvent

logger = logging.getLogger(__name__)

MAX_DOCUMENT_AUDIT_ENTRIES = 500


def append_document_audit_entry(
    access_log: object, entry: Mapping[str, object]
) -> list[dict[str, object]]:
    """Append one audit event while bounding the JSON history column."""
    existing = (
        [item for item in access_log if isinstance(item, dict)]
        if isinstance(access_log, list)
        else []
    )
    existing.append(dict(entry))
    return existing[-MAX_DOCUMENT_AUDIT_ENTRIES:]


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

            # access_log is a JSON array, so concurrent read-modify-write
            # operations can otherwise lose entries. Serialize appenders at
            # the document row, preserving the audit trail under concurrent
            # downloads, reviews, and worker transitions.
            stmt = select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
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

            doc.access_log = append_document_audit_entry(doc.access_log, access_entry)
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(doc, "access_log")

            await session.commit()
            logger.info(f"Logged {action} on document {document_id} by user {user_id}")

    async def log_profile_access(
        self,
        *,
        actor_id: str,
        action: str,
        crew_member_id: str | None = None,
        result_count: int | None = None,
    ) -> None:
        """Record a profile read without storing query text or profile data."""
        try:
            async with get_session_factory()() as session:
                details = {"result_count": result_count} if result_count is not None else None
                session.add(
                    ProfileAccessEvent(
                        actor_id=actor_id,
                        crew_member_id=crew_member_id,
                        action=action,
                        details=details,
                    )
                )
                await session.commit()
        except Exception as exc:
            # Access telemetry must not turn an authorized profile read into
            # an outage. The audit failure remains observable without
            # exposing database/provider details to the caller.
            logger.warning("Could not record profile access audit (%s)", type(exc).__name__)

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

            stmt = select(DocumentModel).where(DocumentModel.id == document_id).with_for_update()
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

            doc.access_log = append_document_audit_entry(doc.access_log, extraction_entry)
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
