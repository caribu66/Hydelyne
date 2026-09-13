"""Shared document-processing claim rules."""

from datetime import datetime, timedelta, timezone

PROCESSING_LEASE = timedelta(minutes=15)


def processing_claim_is_stale(
    processing_started_at: datetime | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether a crashed extraction worker's claim can be recovered."""
    if processing_started_at is None:
        return True
    current = now or datetime.now(timezone.utc)
    started = processing_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return current - started >= PROCESSING_LEASE
