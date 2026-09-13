from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.domain.document_processing import processing_claim_is_stale
from app.services.sync_processor import (
    _final_extraction_status,
    _log_extraction_sync,
    _reset_cv_review_decision,
)


def test_processing_claim_recovery_distinguishes_live_and_stale_workers():
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)

    assert not processing_claim_is_stale(now - timedelta(minutes=1), now=now)
    assert processing_claim_is_stale(now - timedelta(minutes=15), now=now)
    assert processing_claim_is_stale(None, now=now)


def test_sync_reprocessing_cv_clears_stale_review_decision():
    review = SimpleNamespace(
        status="approved",
        approved_data={"full_name": "Old Name"},
        reviewed_by="admin-1",
        review_note="Approved old snapshot",
        reviewed_at="old-time",
    )

    _reset_cv_review_decision(review)

    assert review.status == "awaiting_review"
    assert review.approved_data is None
    assert review.reviewed_by is None
    assert review.review_note is None
    assert review.reviewed_at is None


def test_sync_reprocessing_approved_cv_without_evidence_stays_in_review():
    assert (
        _final_extraction_status(
            "cv",
            "awaiting_review",
            approved_without_evidence=True,
        )
        == "awaiting_review"
    )


def test_sync_reprocessing_approved_non_cv_without_evidence_reopens_review():
    assert (
        _final_extraction_status(
            "certificate",
            "extracted",
            approved_without_evidence=True,
        )
        == "needs_review"
    )


def test_sync_extraction_audit_bridge_records_worker_event():
    audit = AsyncMock()
    dispose = AsyncMock()
    with (
        patch("app.services.audit.audit_service.log_extraction", audit),
        patch("app.database.dispose_engine", dispose),
    ):
        _log_extraction_sync(
            "document-1",
            model_used="llama3.1:8b",
            confidence={"expiry_date": 0.95},
            status="extracted",
        )

    audit.assert_awaited_once_with(
        document_id="document-1",
        model_used="llama3.1:8b",
        confidence={"expiry_date": 0.95},
        status="extracted",
    )
    dispose.assert_awaited_once()


def test_sync_extraction_audit_bridge_does_not_fail_extraction_on_audit_error():
    audit = AsyncMock(side_effect=RuntimeError("audit unavailable"))
    dispose = AsyncMock()
    with (
        patch("app.services.audit.audit_service.log_extraction", audit),
        patch("app.database.dispose_engine", dispose),
    ):
        _log_extraction_sync(
            "document-1",
            model_used="llama3.1:8b",
            confidence={},
            status="failed",
        )

    audit.assert_awaited_once()
    dispose.assert_awaited_once()
