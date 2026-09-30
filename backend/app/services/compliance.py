from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

import redis
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.domain.certifications import is_medical_cert_type
from app.domain.crew_accounts import is_contractor_profile
from app.models import Certification, CrewMember
from app.models import Document as DocumentModel
from app.services.audit import append_document_audit_entry
from app.services.certification_projection import counts_as_medical_evidence

logger = logging.getLogger(__name__)

# Offshore crewing compliance alert windows
ALERT_WINDOW_EXPIRED = "expired"
ALERT_WINDOW_30D = "urgent_30d"
ALERT_WINDOW_60D = "warning_60d"
ALERT_WINDOW_90D = "notice_90d"


def classify_certification_expiry(
    expiry_date: Optional[date],
    reference_date: Optional[date] = None,
) -> dict[str, Any]:
    """Classify a certificate's expiry status against offshore compliance windows.

    Windows:
    - expired: days_remaining < 0 (critical compliance breach)
    - urgent_30d: 0 <= days_remaining <= 30 (urgent renewal required, status = expiring_soon)
    - warning_60d: 31 <= days_remaining <= 60 (mobilization warning)
    - notice_90d: 61 <= days_remaining <= 90 (advance planning / booking window)
    - compliant: > 90 days remaining or no expiry date recorded
    """
    if expiry_date is None:
        return {
            "days_remaining": None,
            "window": "none",
            "urgency": "none",
            "should_transition_status": False,
            "target_status": None,
        }

    ref = reference_date or date.today()
    days_remaining = (expiry_date - ref).days

    if days_remaining < 0:
        return {
            "days_remaining": days_remaining,
            "window": ALERT_WINDOW_EXPIRED,
            "urgency": "critical",
            "should_transition_status": True,
            "target_status": "expired",
        }
    if days_remaining <= 30:
        return {
            "days_remaining": days_remaining,
            "window": ALERT_WINDOW_30D,
            "urgency": "urgent",
            "should_transition_status": True,
            "target_status": "expiring_soon",
        }
    if days_remaining <= 60:
        return {
            "days_remaining": days_remaining,
            "window": ALERT_WINDOW_60D,
            "urgency": "warning",
            "should_transition_status": False,
            "target_status": None,
        }
    if days_remaining <= 90:
        return {
            "days_remaining": days_remaining,
            "window": ALERT_WINDOW_90D,
            "urgency": "notice",
            "should_transition_status": False,
            "target_status": None,
        }

    return {
        "days_remaining": days_remaining,
        "window": "compliant",
        "urgency": "compliant",
        "should_transition_status": False,
        "target_status": "valid",
    }


def _get_sync_redis_client() -> redis.Redis:
    """Build a short-lived sync Redis client for this module's Celery-task callers."""
    from app.config import get_settings

    settings = get_settings()
    # redis-py ships py.typed, but `from_url` itself has no parameter/return
    # annotations in its own source (same finding as cache.py's async
    # equivalent) — genuinely unclassifiable by mypy, not a stub gap.
    client: redis.Redis = redis.from_url(  # type: ignore[no-untyped-call]
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    return client


class ComplianceAlertService:
    """Service for evaluating certification compliance, updating statuses, and emitting alerts."""

    def evaluate_and_update_compliance_sync(
        self,
        session: Session,
        reference_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """Synchronously evaluate certifications, apply status transitions, record audit logs,

        and emit compliance alerts. Designed for the periodic Celery task and batch compliance checks.
        """
        ref_date = reference_date or date.today()
        logger.info(f"Running compliance evaluation for reference date: {ref_date}")

        alerts: dict[str, list[dict[str, Any]]] = {
            ALERT_WINDOW_EXPIRED: [],
            ALERT_WINDOW_30D: [],
            ALERT_WINDOW_60D: [],
            ALERT_WINDOW_90D: [],
        }

        updated_count = 0
        affected_crew_ids: set[str] = set()
        last_id = ""
        batch_size = 200

        while True:
            stmt = (
                select(Certification)
                .join(CrewMember, Certification.crew_member_id == CrewMember.id)
                .where(
                    CrewMember.password_hash.is_(None),
                    or_(
                        CrewMember.role.is_(None),
                        CrewMember.role.not_in(("staff", "admin")),
                    ),
                    Certification.expiry_date.isnot(None),
                    or_(
                        Certification.status.is_(None),
                        Certification.status != "rejected",
                    ),
                    or_(
                        Certification.verification_status.is_(None),
                        Certification.verification_status != "rejected",
                    ),
                    Certification.id > last_id,
                )
                .options(selectinload(Certification.crew_member))
                .order_by(Certification.id)
                .limit(batch_size)
                .with_for_update()
            )
            batch = list(session.execute(stmt).scalars().all())
            if not batch:
                break

            for cert in batch:
                if cert.expiry_date is None:
                    continue

                classification = classify_certification_expiry(cert.expiry_date, ref_date)
                window = classification["window"]
                days_remaining = classification["days_remaining"]
                urgency = classification["urgency"]

                crew: Optional[CrewMember] = cert.crew_member
                crew_name = crew.full_name if crew else "Unknown"
                crew_email = crew.email if crew else None

                old_status = cert.status
                new_status: Optional[str] = None

                if days_remaining is not None:
                    if days_remaining < 0:
                        target_status = "expired"
                    elif days_remaining <= 30:
                        target_status = "expiring_soon"
                    else:
                        target_status = "valid"
                    # Reconcile the date-derived lifecycle state in both
                    # directions. Renewed certificates must recover from a
                    # stale expiring/expired status instead of remaining
                    # permanently non-compliant.
                    if cert.status in {"valid", "expiring_soon", "expired"}:
                        if cert.status != target_status:
                            new_status = target_status

                if new_status and new_status != old_status:
                    cert.status = new_status
                    updated_count += 1
                    affected_crew_ids.add(cert.crew_member_id)

                    if cert.document_ref:
                        # access_log is a JSON array; lock the document before
                        # appending so this worker cannot overwrite a
                        # concurrent download or extraction audit event.
                        doc = session.get(
                            DocumentModel,
                            cert.document_ref,
                            with_for_update=True,
                        )
                        if doc:
                            doc.access_log = append_document_audit_entry(
                                doc.access_log,
                                {
                                    "event": "compliance_status_transition",
                                    "action": "status_changed",
                                    "cert_type": cert.cert_type,
                                    "from_status": old_status,
                                    "to_status": new_status,
                                    "days_remaining": days_remaining,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "reason": "periodic_compliance_check",
                                },
                            )
                            flag_modified(doc, "access_log")

                # Status maintenance applies to every non-rejected source
                # row, including unpublished drafts. The alert snapshot is a
                # shared operational projection, however, so never publish
                # identity, contact, certificate, or document references for
                # an unpublished/orphaned contractor or unverified evidence.
                if (
                    window not in alerts
                    or cert.verification_status != "verified"
                    or crew is None
                    or not is_contractor_profile(crew)
                    or crew.publication_status != "approved"
                ):
                    continue

                if window in alerts:
                    alert_item = {
                        "certification_id": cert.id,
                        "crew_member_id": cert.crew_member_id,
                        "crew_name": crew_name,
                        "crew_email": crew_email,
                        "cert_type": cert.cert_type,
                        "cert_number": cert.cert_number,
                        "document_ref": cert.document_ref,
                        "expiry_date": cert.expiry_date.isoformat(),
                        "days_remaining": days_remaining,
                        "urgency": urgency,
                        "status": cert.status,
                    }
                    alerts[window].append(alert_item)

                    if urgency == "critical":
                        logger.warning(
                            "COMPLIANCE ALERT [CRITICAL/EXPIRED]: crew_id=%s days_remaining=%d",
                            cert.crew_member_id,
                            abs(days_remaining or 0),
                        )
                    elif urgency == "urgent":
                        logger.warning(
                            "COMPLIANCE ALERT [URGENT/30-DAY]: crew_id=%s days_remaining=%d",
                            cert.crew_member_id,
                            days_remaining,
                        )
                    elif urgency == "warning":
                        logger.info(
                            "COMPLIANCE ALERT [WARNING/60-DAY]: crew_id=%s days_remaining=%d",
                            cert.crew_member_id,
                            days_remaining,
                        )
                    elif urgency == "notice":
                        logger.info(
                            "COMPLIANCE ALERT [NOTICE/90-DAY]: crew_id=%s days_remaining=%d",
                            cert.crew_member_id,
                            days_remaining,
                        )

            session.commit()
            last_id = batch[-1].id

        if affected_crew_ids:
            # Recompute the denormalized medical projection from all current
            # evidence. An older certificate may expire while a newer one for
            # the same contractor is still valid. Batched into two queries
            # regardless of crew count instead of two round-trips per crew.
            crew_ids = sorted(affected_crew_ids)
            crews = {
                crew.id: crew
                for crew in session.execute(
                    select(CrewMember).where(CrewMember.id.in_(crew_ids)).with_for_update()
                ).scalars()
            }
            expiries_by_crew: dict[str, list[date]] = {crew_id: [] for crew_id in crew_ids}
            for cert in session.execute(
                select(Certification).where(Certification.crew_member_id.in_(crew_ids))
            ).scalars():
                if (
                    cert.expiry_date
                    and is_medical_cert_type(cert.cert_type)
                    and counts_as_medical_evidence(cert)
                ):
                    expiries_by_crew[cert.crew_member_id].append(cert.expiry_date)
            for crew_id in crew_ids:
                crew = crews.get(crew_id)
                if crew is None:
                    continue
                medical_dates = expiries_by_crew[crew_id]
                replacement_expiry = max(medical_dates) if medical_dates else None
                crew.medical_expiry = replacement_expiry
                crew.medical_status = (
                    ("fit" if replacement_expiry and replacement_expiry >= ref_date else "expired")
                    if replacement_expiry
                    else None
                )
            session.commit()

        self._invalidate_caches_sync(affected_crew_ids)

        total_alerts = sum(len(items) for items in alerts.values())
        summary = {
            ALERT_WINDOW_EXPIRED: len(alerts[ALERT_WINDOW_EXPIRED]),
            ALERT_WINDOW_30D: len(alerts[ALERT_WINDOW_30D]),
            ALERT_WINDOW_60D: len(alerts[ALERT_WINDOW_60D]),
            ALERT_WINDOW_90D: len(alerts[ALERT_WINDOW_90D]),
            "total_alerts": total_alerts,
        }

        result: dict[str, Any] = {
            "status": "completed",
            "reference_date": ref_date.isoformat(),
            "updated": updated_count,
            "invalidated_crew_count": len(affected_crew_ids),
            "summary": summary,
            "alerts": alerts,
        }

        self._publish_alerts_sync(result)
        return result

    def _invalidate_caches_sync(self, crew_ids: set[str]) -> None:
        """Invalidate Redis compliance and crew caches for affected consultants."""
        if not crew_ids:
            return
        try:
            client = _get_sync_redis_client()
            for crew_id in crew_ids:
                # Must match CacheService._make_key("compliance", crew_id):
                # f"compliance:{json.dumps([crew_id])}:{{}}"
                key_data = f"compliance:{json.dumps([crew_id], sort_keys=True, default=str)}:{json.dumps({}, sort_keys=True, default=str)}"
                hashed = hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()
                client.delete(f"hydenlyne:compliance:{hashed}")
                summary_key_data = f"summary:{json.dumps([crew_id], sort_keys=True, default=str)}:{json.dumps({}, sort_keys=True, default=str)}"
                summary_hashed = hashlib.md5(
                    summary_key_data.encode(), usedforsecurity=False
                ).hexdigest()
                client.delete(f"hydenlyne:summary:{summary_hashed}")
            client.close()
        except Exception as e:
            logger.debug(
                "Redis compliance cache invalidation skipped or failed: %s",
                type(e).__name__,
            )

    def _publish_alerts_sync(self, payload: dict[str, Any]) -> None:
        """Publish compliance alert snapshot and event to Redis."""
        try:
            client = _get_sync_redis_client()
            client.set(
                "hydenlyne:compliance:latest_alerts",
                json.dumps(payload, default=str),
                ex=86400,
            )
            client.publish(
                "compliance.alerts",
                json.dumps(
                    {
                        "event": "compliance_evaluation_completed",
                        "summary": payload.get("summary", {}),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    default=str,
                ),
            )
            client.close()
        except Exception as e:
            logger.debug("Redis compliance publish skipped or failed: %s", type(e).__name__)


compliance_service = ComplianceAlertService()
