from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.models import Certification, CrewMember
from app.models import Document as DocumentModel

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
    return redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


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
                .where(Certification.expiry_date.isnot(None), Certification.id > last_id)
                .options(selectinload(Certification.crew_member))
                .order_by(Certification.id)
                .limit(batch_size)
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

                if days_remaining is not None and days_remaining < 0:
                    if cert.status != "expired":
                        new_status = "expired"
                elif days_remaining is not None and days_remaining <= 30:
                    if cert.status == "valid":
                        new_status = "expiring_soon"

                if new_status and new_status != old_status:
                    cert.status = new_status
                    updated_count += 1
                    affected_crew_ids.add(cert.crew_member_id)

                    if "medical" in cert.cert_type.lower() and crew:
                        crew.medical_status = new_status

                    if cert.document_ref:
                        doc = session.get(DocumentModel, cert.document_ref)
                        if doc:
                            access_log = list(doc.access_log or [])
                            access_log.append(
                                {
                                    "event": "compliance_status_transition",
                                    "action": "status_changed",
                                    "cert_type": cert.cert_type,
                                    "from_status": old_status,
                                    "to_status": new_status,
                                    "days_remaining": days_remaining,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "reason": "periodic_compliance_check",
                                }
                            )
                            doc.access_log = access_log
                            flag_modified(doc, "access_log")

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
                            "COMPLIANCE ALERT [CRITICAL/EXPIRED]: %s (%s) - %s expired on %s (%d days ago)",
                            crew_name,
                            cert.crew_member_id,
                            cert.cert_type,
                            cert.expiry_date.isoformat(),
                            abs(days_remaining or 0),
                        )
                    elif urgency == "urgent":
                        logger.warning(
                            "COMPLIANCE ALERT [URGENT/30-DAY]: %s (%s) - %s expires in %d days (%s)",
                            crew_name,
                            cert.crew_member_id,
                            cert.cert_type,
                            days_remaining,
                            cert.expiry_date.isoformat(),
                        )
                    elif urgency == "warning":
                        logger.info(
                            "COMPLIANCE ALERT [WARNING/60-DAY]: %s (%s) - %s expires in %d days (%s)",
                            crew_name,
                            cert.crew_member_id,
                            cert.cert_type,
                            days_remaining,
                            cert.expiry_date.isoformat(),
                        )
                    elif urgency == "notice":
                        logger.info(
                            "COMPLIANCE ALERT [NOTICE/90-DAY]: %s (%s) - %s expires in %d days (%s)",
                            crew_name,
                            cert.crew_member_id,
                            cert.cert_type,
                            days_remaining,
                            cert.expiry_date.isoformat(),
                        )

            session.commit()
            last_id = batch[-1].id

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
                key_data = f"compliance:{crew_id}:{{}}"
                hashed = hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()
                client.delete(f"hydenlyne:compliance:{hashed}")
            client.close()
        except Exception as e:
            logger.debug(f"Redis compliance cache invalidation skipped or failed: {e}")

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
            logger.debug(f"Redis compliance publish skipped or failed: {e}")


compliance_service = ComplianceAlertService()
