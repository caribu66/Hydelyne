"""Tests for compliance evaluation, 30/60/90-day alert windows, and expiration tasks."""

import uuid
from datetime import date, timedelta
from unittest.mock import patch

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


def test_compliance_alert_query_excludes_login_account_rows():
    """The Celery alert evaluator must not mutate account-owned certifications."""

    class EmptyResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class FakeSession:
        statements = []

        def execute(self, statement):
            self.statements.append(statement)
            return EmptyResult()

    fake_session = FakeSession()
    with patch.object(compliance_service, "_publish_alerts_sync"):
        result = compliance_service.evaluate_and_update_compliance_sync(
            fake_session, reference_date=date.today()
        )

    assert result["updated"] == 0
    sql = str(fake_session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "password_hash IS NULL" in sql
    assert "role NOT IN ('staff', 'admin')" in sql


@pytest.mark.asyncio
async def test_expiration_updater_query_excludes_login_account_rows():
    """The periodic updater must not mutate certifications owned by accounts."""

    class EmptyResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class FakeSession:
        statements = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def execute(self, statement):
            self.statements.append(statement)
            return EmptyResult()

    fake_session = FakeSession()
    with patch(
        "app.services.crew.get_session_factory", return_value=lambda: fake_session
    ):
        assert await certification_service.check_and_update_expiration_status() == 0

    sql = str(fake_session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "password_hash IS NULL" in sql
    assert "role NOT IN ('staff', 'admin')" in sql


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
        publication_status="approved",
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
        verification_status="verified",
        document_ref=doc_id,
    )
    # 2. Urgent cert in 30d window (needs status update to "expiring_soon")
    cert_30d = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="BOSIET",
        expiry_date=date(2026, 9, 20),
        status="valid",
        verification_status="verified",
    )
    # 3. Warning cert in 60d window
    cert_60d = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="HUET",
        expiry_date=date(2026, 10, 15),
        status="valid",
        verification_status="verified",
    )
    # 4. Notice cert in 90d window
    cert_90d = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="FOET",
        expiry_date=date(2026, 11, 20),
        status="valid",
        verification_status="verified",
    )
    # 5. Compliant cert (> 90 days)
    cert_ok = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="STCW",
        expiry_date=date(2027, 5, 1),
        status="valid",
        verification_status="verified",
    )
    # 6. Already expired cert (status already "expired", should be in alerts but not re-updated)
    cert_already_expired = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="CA-EBS",
        expiry_date=date(2026, 7, 1),
        status="expired",
        verification_status="verified",
    )
    rejected_future = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="Rejected BOSIET",
        expiry_date=date(2026, 9, 20),
        status="rejected",
    )

    db_session.add_all(
        [
            cert_expired,
            cert_30d,
            cert_60d,
            cert_90d,
            cert_ok,
            cert_already_expired,
            rejected_future,
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
    assert "Rejected BOSIET" not in {
        cert_type
        for window_alerts in result["alerts"].values()
        for cert_type in (alert["cert_type"] for alert in window_alerts)
    }

    # Verify DB persistence
    await db_session.refresh(cert_expired)
    assert cert_expired.status == "expired"

    await db_session.refresh(cert_30d)
    assert cert_30d.status == "expiring_soon"

    await db_session.refresh(rejected_future)
    assert rejected_future.status == "rejected"

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
async def test_sync_compliance_reactivates_renewed_certificates(db_session):
    """Renewed evidence must recover from stale expiry lifecycle states."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Renewed Compliance Crew")
    expiring = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="BOSIET",
        expiry_date=date(2027, 3, 1),
        status="expiring_soon",
    )
    expired = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="HUET",
        expiry_date=date(2026, 10, 15),
        status="expired",
    )
    db_session.add_all([crew, expiring, expired])
    await db_session.commit()

    from app.services.sync_processor import get_sync_session

    sync_session = get_sync_session()
    try:
        result = compliance_service.evaluate_and_update_compliance_sync(
            sync_session, reference_date=date(2026, 9, 1)
        )
    finally:
        sync_session.close()

    assert result["updated"] == 2
    await db_session.refresh(expiring)
    await db_session.refresh(expired)
    assert expiring.status == "valid"
    assert expired.status == "valid"


@pytest.mark.asyncio
async def test_sync_expiration_keeps_newer_medical_projection(db_session):
    """The synchronous compliance worker must preserve newer medical evidence."""
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Sync Overlapping Medical Crew",
        medical_status="fit",
        medical_expiry=date(2026, 12, 1),
    )
    old_cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=date(2026, 8, 20),
        status="valid",
        verification_status="verified",
    )
    current_cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=date(2026, 12, 1),
        status="valid",
        verification_status="verified",
    )
    db_session.add_all([crew, old_cert, current_cert])
    await db_session.commit()

    from app.services.sync_processor import get_sync_session

    sync_session = get_sync_session()
    try:
        compliance_service.evaluate_and_update_compliance_sync(
            sync_session, reference_date=date(2026, 9, 1)
        )
    finally:
        sync_session.close()

    await db_session.refresh(old_cert)
    await db_session.refresh(crew)
    assert old_cert.status == "expired"
    assert crew.medical_expiry == current_cert.expiry_date
    assert crew.medical_status == "fit"


@pytest.mark.asyncio
async def test_compliance_alerts_exclude_unpublished_profiles(db_session):
    """Draft contractor evidence may be updated but must not enter shared alerts."""
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Unpublished Compliance Draft",
        email="draft@example.com",
        publication_status="draft",
        submitted_by="staff-1",
    )
    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="BOSIET",
        expiry_date=date(2026, 9, 20),
        status="valid",
        verification_status="verified",
        cert_number="PRIVATE-DRAFT-CERT",
    )
    db_session.add_all([crew, cert])
    await db_session.commit()

    from app.services.sync_processor import get_sync_session

    sync_session = get_sync_session()
    try:
        result = compliance_service.evaluate_and_update_compliance_sync(
            sync_session, reference_date=date(2026, 9, 1)
        )
    finally:
        sync_session.close()

    alert_items = [alert for alerts in result["alerts"].values() for alert in alerts]
    assert all(alert["crew_member_id"] != crew.id for alert in alert_items)
    assert all(alert["cert_number"] != "PRIVATE-DRAFT-CERT" for alert in alert_items)

    await db_session.refresh(cert)
    assert cert.status == "expiring_soon"


@pytest.mark.asyncio
async def test_compliance_alerts_exclude_unverified_evidence(db_session):
    """Unverified lifecycle rows must not become shared compliance alerts."""
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Unverified Compliance Evidence",
        publication_status="approved",
    )
    cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="BOSIET",
        expiry_date=date.today() + timedelta(days=10),
        status="expiring_soon",
        verification_status="unverified",
    )
    db_session.add_all([crew, cert])
    await db_session.commit()

    from app.services.sync_processor import get_sync_session

    sync_session = get_sync_session()
    try:
        result = compliance_service.evaluate_and_update_compliance_sync(sync_session)
    finally:
        sync_session.close()

    alert_items = [alert for alerts in result["alerts"].values() for alert in alerts]
    assert all(alert["crew_member_id"] != crew.id for alert in alert_items)


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
        verification_status="verified",
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
        verification_status="verified",
    )
    db_session.add(cert)
    await db_session.commit()

    updated = await certification_service.check_and_update_expiration_status()
    assert updated >= 1

    await db_session.refresh(cert)
    assert cert.status == "expired"

    await db_session.refresh(crew)
    assert crew.medical_status == "expired"


@pytest.mark.asyncio
async def test_async_expiration_checker_reactivates_renewed_certificates(db_session):
    """The async checker must restore date-valid renewed certificates."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Async Renewed Crew")
    expiring = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="BOSIET",
        expiry_date=date.today() + timedelta(days=180),
        status="expiring_soon",
    )
    expired = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="HUET",
        expiry_date=date.today() + timedelta(days=90),
        status="expired",
    )
    db_session.add_all([crew, expiring, expired])
    await db_session.commit()

    updated = await certification_service.check_and_update_expiration_status()

    assert updated >= 2
    await db_session.refresh(expiring)
    await db_session.refresh(expired)
    assert expiring.status == "valid"
    assert expired.status == "valid"


@pytest.mark.asyncio
async def test_expiring_old_medical_does_not_hide_newer_valid_medical(db_session):
    """Root medical status must follow the newest remaining medical evidence."""
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Overlapping Medical Crew",
        medical_status="fit",
        medical_expiry=date.today() + timedelta(days=180),
    )
    old_cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=date.today() - timedelta(days=1),
        status="valid",
        verification_status="verified",
    )
    current_cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=date.today() + timedelta(days=180),
        status="valid",
        verification_status="verified",
    )
    db_session.add_all([crew, old_cert, current_cert])
    await db_session.commit()

    await certification_service.check_and_update_expiration_status()

    await db_session.refresh(old_cert)
    await db_session.refresh(crew)
    assert old_cert.status == "expired"
    assert crew.medical_expiry == current_cert.expiry_date
    assert crew.medical_status == "fit"


@pytest.mark.asyncio
async def test_sync_medical_recompute_is_batched_not_per_crew(db_session, monkeypatch):
    """The periodic recompute must not issue two round-trips per affected crew:
    one crew SELECT and one certification SELECT cover every affected crew."""
    ref_date = date(2026, 9, 1)
    crews = [
        CrewMember(id=str(uuid.uuid4()), full_name=f"Batched Recompute Crew {i}") for i in range(3)
    ]
    db_session.add_all(crews)
    # Each crew gets a transitioning driver cert plus distinct medical evidence.
    drivers = [
        Certification(
            id=str(uuid.uuid4()),
            crew_member_id=crews[i].id,
            cert_type="BOSIET",
            expiry_date=date(2026, 9, 11),
            status="valid",
        )
        for i in range(3)
    ]
    medicals = [
        Certification(  # expired verified medical -> recompute yields expired
            id=str(uuid.uuid4()),
            crew_member_id=crews[0].id,
            cert_type="OGUK Medical",
            expiry_date=date(2026, 8, 20),
            status="valid",
            verification_status="verified",
        ),
        Certification(  # future verified medical -> recompute yields fit
            id=str(uuid.uuid4()),
            crew_member_id=crews[1].id,
            cert_type="OGUK Medical",
            expiry_date=date(2027, 5, 1),
            status="valid",
            verification_status="verified",
        ),
    ]
    db_session.add_all(drivers + medicals)
    await db_session.commit()

    from app.services.sync_processor import get_sync_session

    sync_session = get_sync_session()
    statements: list[str] = []
    real_execute = sync_session.execute

    def _counting_execute(statement: object, *args: object, **kwargs: object) -> object:
        statements.append(
            str(
                statement.compile(compile_kwargs={"literal_binds": True})  # type: ignore[union-attr]
            )
        )
        return real_execute(statement, *args, **kwargs)

    monkeypatch.setattr(sync_session, "execute", _counting_execute)
    try:
        result = compliance_service.evaluate_and_update_compliance_sync(
            sync_session, reference_date=ref_date
        )
    finally:
        sync_session.close()

    assert result["updated"] == 4
    crew_selects = [sql for sql in statements if "FROM crew_members" in sql]
    cert_selects = [sql for sql in statements if "FROM certifications" in sql]
    # Two batched cert scans (rows, then empty) plus one batched recompute
    # select each; the crew count includes the scan's selectin-load of the
    # crew relationship. The old per-crew loop needed three recompute selects
    # of each kind for three crews (four crew selects, five cert selects).
    assert len(crew_selects) == 2
    assert len(cert_selects) == 3

    await db_session.refresh(crews[0])
    await db_session.refresh(crews[1])
    await db_session.refresh(crews[2])
    assert crews[0].medical_status == "expired"
    assert crews[1].medical_status == "fit"
    assert crews[2].medical_status is None
