"""Tests for compliance evaluation, 30/60/90-day alert windows, and expiration tasks."""

import uuid
from datetime import date, timedelta

import pytest

from app.models import Certification, CrewMember, Document
from app.services.compliance import (
    ALERT_WINDOW_30D,
    ALERT_WINDOW_60D,
    ALERT_WINDOW_90D,
    ALERT_WINDOW_EXPIRED,
    classify_certification_expiry,
    compliance_service,
)
from app.services.crew import certification_service
from app.tasks.document_tasks import check_expiring_certifications


def test_classify_certification_expiry_windows():
    """Verify that dates map deterministically into the offshore compliance windows."""
    ref = date(2026, 9, 1)

    # 1. No expiry date
    res_none = classify_certification_expiry(None, ref)
    assert res_none["window"] == "none"
    assert res_none["urgency"] == "none"
    assert not res_none["should_transition_status"]

    # 2. Expired (< 0 days)
    res_exp = classify_certification_expiry(date(2026, 8, 25), ref)
    assert res_exp["window"] == ALERT_WINDOW_EXPIRED
    assert res_exp["urgency"] == "critical"
    assert res_exp["should_transition_status"]
    assert res_exp["target_status"] == "expired"
    assert res_exp["days_remaining"] == -7

    # 3. Urgent (0 to 30 days)
    res_30 = classify_certification_expiry(date(2026, 9, 15), ref)
    assert res_30["window"] == ALERT_WINDOW_30D
    assert res_30["urgency"] == "urgent"
    assert res_30["should_transition_status"]
    assert res_30["target_status"] == "expiring_soon"
    assert res_30["days_remaining"] == 14

    # 4. Warning (31 to 60 days)
    res_60 = classify_certification_expiry(date(2026, 10, 20), ref)
    assert res_60["window"] == ALERT_WINDOW_60D
    assert res_60["urgency"] == "warning"
    assert not res_60["should_transition_status"]
    assert res_60["days_remaining"] == 49

    # 5. Notice (61 to 90 days)
    res_90 = classify_certification_expiry(date(2026, 11, 15), ref)
    assert res_90["window"] == ALERT_WINDOW_90D
    assert res_90["urgency"] == "notice"
    assert not res_90["should_transition_status"]
    assert res_90["days_remaining"] == 75

    # 6. Compliant (> 90 days)
    res_ok = classify_certification_expiry(date(2027, 3, 1), ref)
    assert res_ok["window"] == "compliant"
    assert res_ok["urgency"] == "compliant"
    assert not res_ok["should_transition_status"]


@pytest.mark.asyncio
async def test_evaluate_and_update_compliance_sync(db_session):
    """Verify that evaluate_and_update_compliance_sync updates statuses, records

    audit entries, syncs medical state, and groups alerts by window.
    """
    ref_date = date(2026, 9, 1)

    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Captain David Evans",
        email="devans@example.com",
        role="user",
        medical_status="fit",
    )
    db_session.add(crew)

    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        crew_member_id=crew.id,
        file_name="medical_cert.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_type="local",
        storage_path="/tmp/medical_cert.pdf",
        classification="compliance",
        extraction_status="extracted",
        access_log=[],
    )
    db_session.add(doc)

    # 1. Expired medical cert (needs status update to "expired" and crew medical update)
    cert_expired = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=date(2026, 8, 20),
        status="valid",
        document_ref=doc_id,
    )
    # 2. Urgent cert in 30d window (needs status update to "expiring_soon")
    cert_30d = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="BOSIET",
        expiry_date=date(2026, 9, 20),
        status="valid",
    )
    # 3. Warning cert in 60d window
    cert_60d = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="HUET",
        expiry_date=date(2026, 10, 15),
        status="valid",
    )
    # 4. Notice cert in 90d window
    cert_90d = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="FOET",
        expiry_date=date(2026, 11, 20),
        status="valid",
    )
    # 5. Compliant cert (> 90 days)
    cert_ok = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="STCW",
        expiry_date=date(2027, 5, 1),
        status="valid",
    )
    # 6. Already expired cert (status already "expired", should be in alerts but not re-updated)
    cert_already_expired = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="CA-EBS",
        expiry_date=date(2026, 7, 1),
        status="expired",
    )

    db_session.add_all(
        [
            cert_expired,
            cert_30d,
            cert_60d,
            cert_90d,
            cert_ok,
            cert_already_expired,
        ]
    )
    await db_session.commit()

    from app.services.sync_processor import get_sync_session

    sync_session = get_sync_session()
    try:
        result = compliance_service.evaluate_and_update_compliance_sync(
            sync_session, reference_date=ref_date
        )
    finally:
        sync_session.close()

    assert result["status"] == "completed"
    assert result["reference_date"] == ref_date.isoformat()
    # Exactly 2 certs updated: cert_expired (valid -> expired) and cert_30d (valid -> expiring_soon)
    assert result["updated"] == 2
    assert result["invalidated_crew_count"] == 1

    summary = result["summary"]
    assert summary[ALERT_WINDOW_EXPIRED] == 2
    assert summary[ALERT_WINDOW_30D] == 1
    assert summary[ALERT_WINDOW_60D] == 1
    assert summary[ALERT_WINDOW_90D] == 1
    assert summary["total_alerts"] == 5

    # Check alert contents
    expired_alerts = result["alerts"][ALERT_WINDOW_EXPIRED]
    expired_types = {a["cert_type"] for a in expired_alerts}
    assert "OGUK Medical" in expired_types
    assert "CA-EBS" in expired_types

    # Verify DB persistence
    await db_session.refresh(cert_expired)
    assert cert_expired.status == "expired"

    await db_session.refresh(cert_30d)
    assert cert_30d.status == "expiring_soon"

    await db_session.refresh(cert_60d)
    assert cert_60d.status == "valid"

    await db_session.refresh(crew)
    assert crew.medical_status == "expired"

    # Verify backing document access_log recorded the transition
    await db_session.refresh(doc)
    logs = doc.access_log or []
    assert len(logs) == 1
    assert logs[0]["event"] == "compliance_status_transition"
    assert logs[0]["from_status"] == "valid"
    assert logs[0]["to_status"] == "expired"
    assert logs[0]["cert_type"] == "OGUK Medical"


@pytest.mark.asyncio
async def test_expiring_soon_cert_does_not_leak_into_medical_status(db_session):
    """Cert lifecycle vocab must not leak into the crew fitness flag.

    medical_status uses MEDICAL_STATUS_VALUES (fit/fit_with_restrictions/
    expired); an "expiring_soon" cert transition must leave it as "fit".
    """
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Nia Okafor",
        role="user",
        medical_status="fit",
    )
    db_session.add(crew)
    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=date.today() + timedelta(days=10),
        status="valid",
    )
    db_session.add(cert)
    await db_session.commit()

    updated = await certification_service.check_and_update_expiration_status()
    assert updated >= 1

    await db_session.refresh(cert)
    assert cert.status == "expiring_soon"
    await db_session.refresh(crew)
    assert crew.medical_status == "fit"


@pytest.mark.asyncio
async def test_check_expiring_certifications_celery_task(db_session):
    """The check_expiring_certifications Celery task must execute cleanly."""
    result = check_expiring_certifications()
    assert result["status"] == "completed"
    assert "summary" in result
    assert "alerts" in result


@pytest.mark.asyncio
async def test_async_check_and_update_expiration_status_transitions_expiring_soon_to_expired(
    db_session,
):
    """When an expiring_soon ticket passes its expiry date, check_and_update_expiration_status

    must transition it to 'expired' and keep medical fields in sync.
    """
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Elena Rostova",
        role="user",
        medical_status="expiring_soon",
    )
    db_session.add(crew)

    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=date.today() - timedelta(days=2),
        status="expiring_soon",
    )
    db_session.add(cert)
    await db_session.commit()

    updated = await certification_service.check_and_update_expiration_status()
    assert updated >= 1

    await db_session.refresh(cert)
    assert cert.status == "expired"

    await db_session.refresh(crew)
    assert crew.medical_status == "expired"
