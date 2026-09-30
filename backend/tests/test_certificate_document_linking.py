"""Tests for standalone certificate document ingestion and Certification linking."""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import get_session_factory
from app.domain.certifications import is_medical_cert_type, normalize_cert_name
from app.domain.fields import normalize_classification
from app.models import (
    Certification,
    CrewMember,
    CVReview,
    Document,
    DocumentRequest,
    IncomingDocumentReview,
)
from app.services.certification_projection import (
    reconcile_medical_profile,
    reconcile_medical_profile_after_detachment,
)
from app.services.crew import certification_service
from app.services.document_service import document_service
from app.services.extraction import extraction_service
from app.services.text_extraction import text_extraction_service


async def _add_extracted_certificate_document(session, crew_id: str, document_id: str) -> None:
    session.add(
        Document(
            id=document_id,
            crew_member_id=crew_id,
            file_name="certificate.pdf",
            file_type="pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="certificate",
            extraction_status="extracted",
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_medical_projection_ignores_login_account_rows():
    """Legacy account certifications must not populate account medical fields."""

    class Result:
        def scalar_one_or_none(self):
            return account

    class FakeSession:
        execute_count = 0

        async def execute(self, _statement):
            self.execute_count += 1
            return Result()

    account = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Staff account",
        password_hash="hashed",
        role="staff",
        medical_status="fit",
        medical_expiry=date(2030, 1, 1),
    )
    session = FakeSession()

    await reconcile_medical_profile(session, crew_id=account.id)
    await reconcile_medical_profile_after_detachment(
        session,
        crew_id=account.id,
        detached_certification_ids=["certificate-1"],
        detached_expiry_dates=[date(2030, 1, 1)],
    )

    assert session.execute_count == 2
    assert account.medical_status == "fit"
    assert account.medical_expiry == date(2030, 1, 1)


@pytest.mark.asyncio
async def test_async_extraction_rejects_auto_classified_contractor_cv(db_session):
    """Omitted upload classification must not enter the staff CV workflow."""
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Contractor CV", publication_status="approved"))
    db_session.add(
        DocumentRequest(
            id=request_id,
            crew_member_id=crew_id,
            token_hash="x" * 64,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
            created_by="staff-1",
        )
    )
    document = Document(
        id=document_id,
        crew_member_id=crew_id,
        file_name="resume.pdf",
        file_type="pdf",
        file_size=10,
        storage_type="local",
        storage_path=f"/tmp/{document_id}.pdf",
        classification=None,
        extraction_status="pending",
        uploaded_by="contractor-upload-link",
    )
    db_session.add(document)
    db_session.add(
        IncomingDocumentReview(
            request_id=request_id,
            document_id=document_id,
        )
    )
    await db_session.commit()

    with (
        patch(
            "app.services.document_service.document_upload_service.get_file_async",
            new=AsyncMock(return_value=b"%PDF-1.4 current"),
        ),
        patch(
            "app.services.document_service.text_extraction_service.extract_text",
            new=AsyncMock(return_value="CV text"),
        ),
        patch(
            "app.services.document_service.extraction_service.classify_document",
            new=AsyncMock(return_value={"classification": "cv"}),
        ),
        patch(
            "app.services.cv_processing.CVProcessingService.extract_cv_deterministically",
            return_value={"document_type": "cv", "full_name": "Contractor CV"},
        ),
        patch(
            "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await document_service.process_document(document_id)

    assert result["status"] == "rejected"
    await db_session.refresh(document)
    assert document.extraction_status == "rejected"
    incoming_review = (
        await db_session.execute(
            select(IncomingDocumentReview).where(IncomingDocumentReview.document_id == document_id)
        )
    ).scalar_one()
    assert incoming_review.status == "rejected"
    assert (
        await db_session.execute(select(CVReview).where(CVReview.document_id == document_id))
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "certificate_type",
    [["BOSIET"], "x" * 51],
)
async def test_link_extracted_certificate_rejects_malformed_or_oversized_type(
    certificate_type,
):
    with patch("app.services.crew.get_session_factory") as get_factory:
        result = await certification_service.link_extracted_certificate(
            crew_id="crew-1",
            document_id="document-1",
            extracted_data={"certificate_type": certificate_type},
        )

    assert result is None
    get_factory.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_extraction_queues_semantic_projection(db_session):
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Confirmed Extraction Crew"))
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew_id,
            file_name="evidence.pdf",
            file_type="pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="other",
            extraction_status="needs_review",
        )
    )
    await db_session.commit()

    settings = get_settings()
    previous_semantic_flag = settings.ENABLE_SEMANTIC_SEARCH
    settings.ENABLE_SEMANTIC_SEARCH = True
    try:
        with patch(
            "app.tasks.document_tasks.index_document_embeddings.delay",
            new=MagicMock(),
        ) as embedding_delay:
            confirmed = await document_service.confirm_extraction(
                document_id, {"document_type": "other", "confidence": {}}
            )
            embedding_delay.assert_called_once_with(document_id)
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = previous_semantic_flag

    assert confirmed is not None
    assert confirmed.extraction_status == "extracted"


@pytest.mark.asyncio
async def test_confirm_extraction_queues_search_retry_when_provider_raises(db_session):
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Search Retry Crew"))
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew_id,
            file_name="search-retry.pdf",
            file_type="pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="other",
            extraction_status="needs_review",
        )
    )
    await db_session.commit()

    with (
        patch(
            "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
            new=AsyncMock(side_effect=RuntimeError("search unavailable")),
        ),
        patch("app.tasks.document_tasks.queue_document_search_reconcile") as queue_search,
    ):
        confirmed = await document_service.confirm_extraction(
            document_id, {"document_type": "other"}
        )

    assert confirmed is not None
    queue_search.assert_called_once_with(document_id)


@pytest.mark.asyncio
async def test_confirm_contractor_upload_keeps_certificate_review_gated(db_session):
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Review Gated Crew"))
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew_id,
            file_name="contractor-certificate.pdf",
            file_type="pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="certificate",
            extraction_status="needs_review",
            uploaded_by="contractor-upload-link",
        )
    )
    await db_session.commit()

    with patch(
        "app.tasks.document_tasks.index_document_embeddings.delay",
        new=MagicMock(),
    ) as embedding_delay:
        confirmed = await document_service.confirm_extraction(
            document_id,
            {
                "certificate_type": "STCW",
                "expiry_date": (date.today() + timedelta(days=200)).isoformat(),
            },
        )

    assert confirmed is not None
    assert confirmed.extraction_status == "needs_review"
    embedding_delay.assert_not_called()
    linked = (
        await db_session.execute(
            select(Certification).where(Certification.document_ref == document_id)
        )
    ).scalar_one_or_none()
    assert linked is None


@pytest.mark.asyncio
async def test_confirm_extraction_does_not_race_active_worker(db_session):
    """Manual confirmation cannot overwrite an extraction worker in progress."""
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Active Extraction Crew"))
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew_id,
            file_name="active.pdf",
            file_type="application/pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="other",
            extraction_status="processing",
        )
    )
    await db_session.commit()

    with pytest.raises(ValueError, match="currently in progress"):
        await document_service.confirm_extraction(document_id, {"document_type": "other"})


@pytest.mark.asyncio
async def test_relinking_approved_certificate_document_rebuilds_certificate(db_session):
    source = CrewMember(id=str(uuid.uuid4()), full_name="Original Certificate Crew")
    target = CrewMember(id=str(uuid.uuid4()), full_name="Relinked Certificate Crew")
    document_id = str(uuid.uuid4())
    db_session.add_all([source, target])
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=source.id,
            file_name="approved-certificate.pdf",
            file_type="pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="certificate",
            extraction_status="approved",
            extracted_data={
                "certificate_type": "BOSIET",
                "expiry_date": (date.today() + timedelta(days=180)).isoformat(),
            },
        )
    )
    db_session.add(
        Certification(
            crew_member_id=source.id,
            cert_type="BOSIET",
            document_ref=document_id,
            status="valid",
            verification_status="unverified",
        )
    )
    await db_session.commit()

    await document_service.link_to_crew_member(document_id, target.id)

    target_cert = (
        await db_session.execute(
            select(Certification).where(Certification.crew_member_id == target.id)
        )
    ).scalar_one_or_none()
    assert target_cert is not None
    assert target_cert.document_ref == document_id


@pytest.mark.asyncio
async def test_relinking_queues_search_retry_when_provider_raises(db_session):
    source = CrewMember(id=str(uuid.uuid4()), full_name="Relink Source")
    target = CrewMember(id=str(uuid.uuid4()), full_name="Relink Target")
    document_id = str(uuid.uuid4())
    db_session.add_all([source, target])
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=source.id,
            file_name="relink-search-retry.pdf",
            file_type="pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="other",
            extraction_status="extracted",
            extracted_data={"document_type": "other"},
        )
    )
    await db_session.commit()

    with (
        patch(
            "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
            new=AsyncMock(side_effect=RuntimeError("search unavailable")),
        ),
        patch("app.tasks.document_tasks.queue_document_search_reconcile") as queue_search,
    ):
        await document_service.link_to_crew_member(document_id, target.id)

    queue_search.assert_called_once_with(document_id)


def test_normalize_classification_handles_cert_and_aliases():
    """Classification aliases like 'cert' or uppercase strings must normalize
    to the canonical 'certificate' classification."""
    assert normalize_classification("cert") == "certificate"
    assert normalize_classification("CERT") == "certificate"
    assert normalize_classification("certificate") == "certificate"
    assert normalize_classification("certification") == "certificate"
    assert normalize_classification("certificates") == "certificate"
    assert normalize_classification("cv") == "cv"
    assert normalize_classification("resume") == "cv"
    assert normalize_classification("medical") == "compliance"
    assert normalize_classification("seamans_book") == "compliance"
    assert normalize_classification(None) == "other"
    assert normalize_classification("unknown_category") == "other"


def test_normalize_cert_name_recognizes_medical_variants():
    """Medical aliases like offshore_medical, OEUK, and ENG1 must resolve
    to canonical 'OGUK Medical'."""
    assert normalize_cert_name("offshore medical") == "OGUK Medical"
    assert normalize_cert_name("OFFSHORE_MEDICAL") == "OGUK Medical"
    assert normalize_cert_name("oeuk") == "OGUK Medical"
    assert normalize_cert_name("eng1") == "OGUK Medical"
    assert normalize_cert_name("OGUK Medical") == "OGUK Medical"


def test_medical_certificate_detection_matches_frontend_aliases():
    assert is_medical_cert_type("ENG1") is True
    assert is_medical_cert_type("OEUK") is True
    assert is_medical_cert_type("BOSIET") is False


@pytest.mark.asyncio
async def test_link_extracted_certificate_creates_new_certification(db_session):
    """When a consultant uploads a certificate document, link_extracted_certificate
    must create a new Certification row linked to that document_id."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Sarah Jenkins", role="user")
    db_session.add(crew)
    await db_session.commit()

    doc_id = str(uuid.uuid4())
    await _add_extracted_certificate_document(db_session, crew.id, doc_id)
    expiry = date.today() + timedelta(days=365)
    issue = date.today() - timedelta(days=30)

    extracted_data = {
        "document_type": "certificate",
        "certificate_type": "BOSIET",
        "certificate_number": "RN-998877",
        "issuing_body": "RelyOn Nutec",
        "issue_date": issue.isoformat(),
        "expiry_date": expiry.isoformat(),
        "confidence": {"certificate_type": 0.95, "expiry_date": 0.9},
    }

    cert = await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=doc_id,
        extracted_data=extracted_data,
    )

    assert cert is not None
    assert cert.crew_member_id == crew.id
    assert cert.cert_type == "BOSIET"
    assert cert.cert_number == "RN-998877"
    assert cert.issuing_body == "RelyOn Nutec"
    assert cert.issue_date == issue
    assert cert.expiry_date == expiry
    assert cert.document_ref == doc_id
    assert cert.status == "pending_verification"
    assert cert.verification_status == "unverified"
    assert cert.extracted_confidence == pytest.approx(0.925, abs=0.01)


@pytest.mark.asyncio
async def test_link_extracted_certificate_updates_existing_unlinked_cert(db_session):
    """If a certification of the same type already exists for the crew member
    (e.g. populated unverified from CV ingestion without document proof),
    uploading the actual certificate document must attach document_ref and
    backfill details onto the existing row instead of duplicating."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Alan Davis", role="user")
    db_session.add(crew)
    await db_session.flush()

    existing_cert = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="PAMGUARD Advanced",
        status="pending_verification",
        verification_status="unverified",
        document_ref=None,
    )
    db_session.add(existing_cert)
    await db_session.commit()

    doc_id = str(uuid.uuid4())
    await _add_extracted_certificate_document(db_session, crew.id, doc_id)
    expiry = date.today() + timedelta(days=500)
    extracted_data = {
        "document_type": "certificate",
        "certificate_type": "PAMGUARD",
        "certificate_number": "PAM-4455",
        "issuing_body": "Seiche Training",
        "expiry_date": expiry.isoformat(),
    }

    linked_cert = await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=doc_id,
        extracted_data=extracted_data,
    )

    assert linked_cert is not None
    assert linked_cert.id == existing_cert.id  # Same record updated
    assert linked_cert.cert_type == "PAMGUARD Advanced"
    assert linked_cert.document_ref == doc_id
    assert linked_cert.cert_number == "PAM-4455"
    assert linked_cert.issuing_body == "Seiche Training"
    assert linked_cert.expiry_date == expiry

    # Verify database has only 1 certification
    stmt = select(Certification).where(Certification.crew_member_id == crew.id)
    all_certs = (await db_session.execute(stmt)).scalars().all()
    assert len(all_certs) == 1


@pytest.mark.asyncio
async def test_link_extracted_certificate_reprocessing_updates_in_place(db_session):
    """Reprocessing the same document must update the linked certification
    in-place without creating a duplicate record."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Robert Taylor", role="user")
    db_session.add(crew)
    await db_session.commit()

    doc_id = str(uuid.uuid4())
    await _add_extracted_certificate_document(db_session, crew.id, doc_id)
    first_run = {
        "certificate_type": "GWO Wind",
        "issuing_body": "Maersk Training",
        "expiry_date": "2027-06-01",
    }
    cert1 = await certification_service.link_extracted_certificate(
        crew_id=crew.id, document_id=doc_id, extracted_data=first_run
    )
    assert cert1 is not None

    second_run = {
        "certificate_type": "GWO Wind",
        "certificate_number": "GWO-991122",
        "issuing_body": "Maersk Training UK",
        "expiry_date": "2027-06-01",
    }
    cert2 = await certification_service.link_extracted_certificate(
        crew_id=crew.id, document_id=doc_id, extracted_data=second_run
    )
    assert cert2 is not None
    assert cert2.id == cert1.id
    assert cert2.cert_number == "GWO-991122"
    assert cert2.issuing_body == "Maersk Training UK"

    cert2.verification_status = "verified"
    await db_session.commit()
    cert3 = await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=doc_id,
        extracted_data={"certificate_type": "GWO Wind"},
    )
    assert cert3 is not None
    assert cert3.expiry_date is None
    assert cert3.cert_number is None
    assert cert3.issuing_body is None
    assert cert3.status == "pending_verification"
    assert cert3.verification_status == "unverified"

    stmt = select(Certification).where(Certification.crew_member_id == crew.id)
    all_certs = (await db_session.execute(stmt)).scalars().all()
    assert len(all_certs) == 1


@pytest.mark.asyncio
async def test_link_extracted_medical_syncs_to_crew_member_fields(db_session):
    """Extracting an offshore medical certificate must synchronize root medical
    fields on the CrewMember (medical_status, medical_expiry, medical_provider)."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Elena Gomez", role="user")
    db_session.add(crew)
    await db_session.commit()

    doc_id = str(uuid.uuid4())
    await _add_extracted_certificate_document(db_session, crew.id, doc_id)
    expiry = date.today() + timedelta(days=300)
    extracted_data = {
        "certificate_type": "OFFSHORE_MEDICAL",
        "issuing_body": "Aberdeen Health Centre",
        "expiry_date": expiry.isoformat(),
    }

    cert = await certification_service.link_extracted_certificate(
        crew_id=crew.id, document_id=doc_id, extracted_data=extracted_data
    )

    assert cert is not None
    assert cert.cert_type == "OGUK Medical"

    # Reload crew member from database
    await db_session.refresh(crew)
    assert crew.medical_status == "fit"
    assert crew.medical_expiry == expiry
    assert crew.medical_provider == "Aberdeen Health Centre"


@pytest.mark.asyncio
@pytest.mark.parametrize("cert_type", ["OGUK Medical", "ENG1"])
async def test_manual_medical_certification_syncs_crew_projection(db_session, cert_type):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Manual Medical Crew", role="user")
    db_session.add(crew)
    await db_session.commit()

    expiry = date.today() + timedelta(days=180)
    cert = await certification_service.add_certification(
        crew_id=crew.id,
        cert_type=cert_type,
        issuing_body="Manual Clinic",
        expiry_date=expiry,
    )

    assert cert.expiry_date == expiry
    await db_session.refresh(crew)
    assert crew.medical_expiry == expiry
    assert crew.medical_status == "fit"
    assert crew.medical_provider == "Manual Clinic"


@pytest.mark.asyncio
async def test_reprocessing_medical_certificate_can_reduce_root_expiry(db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Medical Correction Crew", role="user")
    db_session.add(crew)
    await db_session.commit()

    doc_id = str(uuid.uuid4())
    await _add_extracted_certificate_document(db_session, crew.id, doc_id)
    first_expiry = date.today() + timedelta(days=300)
    corrected_expiry = date.today() + timedelta(days=30)
    await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=doc_id,
        extracted_data={
            "certificate_type": "OFFSHORE_MEDICAL",
            "expiry_date": first_expiry.isoformat(),
        },
    )
    await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=doc_id,
        extracted_data={
            "certificate_type": "OFFSHORE_MEDICAL",
            "expiry_date": corrected_expiry.isoformat(),
        },
    )

    await db_session.refresh(crew)
    assert crew.medical_expiry == corrected_expiry
    assert crew.medical_status == "fit"


@pytest.mark.asyncio
async def test_rejected_medical_verification_clears_root_projection(db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Rejected Medical Crew", role="user")
    db_session.add(crew)
    await db_session.commit()
    document_id = str(uuid.uuid4())
    await _add_extracted_certificate_document(db_session, crew.id, document_id)
    expiry = date.today() + timedelta(days=200)
    cert = await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=document_id,
        extracted_data={
            "certificate_type": "OFFSHORE_MEDICAL",
            "expiry_date": expiry.isoformat(),
        },
    )
    assert cert is not None

    await certification_service.verify_certification(cert.id, "rejected")

    await db_session.refresh(crew)
    assert crew.medical_expiry is None
    assert crew.medical_status is None


@pytest.mark.asyncio
async def test_detaching_expiryless_medical_evidence_clears_stale_root_projection(db_session):
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Expiryless Medical Crew",
        medical_expiry=date(2030, 1, 1),
        medical_status="fit",
    )
    certification = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        cert_type="OGUK Medical",
        expiry_date=None,
        document_ref=str(uuid.uuid4()),
        status="valid",
        verification_status="verified",
    )
    db_session.add_all([crew, certification])
    await db_session.commit()

    await reconcile_medical_profile_after_detachment(
        db_session,
        crew_id=crew.id,
        detached_certification_ids=[certification.id],
        detached_expiry_dates=[None],
    )
    await db_session.commit()
    await db_session.refresh(crew)

    assert crew.medical_expiry is None
    assert crew.medical_status is None


@pytest.mark.asyncio
async def test_reprocessing_rejected_certificate_reopens_verification(db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Reprocessed Certificate Crew", role="user")
    db_session.add(crew)
    await db_session.commit()
    document_id = str(uuid.uuid4())
    await _add_extracted_certificate_document(db_session, crew.id, document_id)
    cert = await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=document_id,
        extracted_data={
            "certificate_type": "STCW",
            "expiry_date": (date.today() + timedelta(days=200)).isoformat(),
        },
    )
    assert cert is not None

    await certification_service.verify_certification(cert.id, "rejected")
    reopened = await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=document_id,
        extracted_data={
            "certificate_type": "STCW",
            "expiry_date": (date.today() + timedelta(days=200)).isoformat(),
        },
    )

    assert reopened is not None
    assert reopened.verification_status == "unverified"


@pytest.mark.asyncio
async def test_rejected_document_cannot_create_certificate_projection(db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Rejected Evidence Crew", role="user")
    document_id = str(uuid.uuid4())
    db_session.add(crew)
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew.id,
            file_name="rejected-certificate.pdf",
            file_type="pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="certificate",
            extraction_status="rejected",
        )
    )
    await db_session.commit()

    linked = await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=document_id,
        extracted_data={"certificate_type": "BOSIET"},
    )

    assert linked is None


@pytest.mark.asyncio
async def test_contractor_extracted_document_cannot_create_certificate_projection(db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Unapproved Evidence Crew")
    document_id = str(uuid.uuid4())
    db_session.add(crew)
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew.id,
            file_name="contractor-certificate.pdf",
            file_type="pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="certificate",
            extraction_status="extracted",
            uploaded_by="contractor-upload-link",
        )
    )
    await db_session.commit()

    linked = await certification_service.link_extracted_certificate(
        crew_id=crew.id,
        document_id=document_id,
        extracted_data={"certificate_type": "BOSIET"},
    )

    assert linked is None


@pytest.mark.asyncio
async def test_link_extracted_certificate_computes_expired_status(db_session):
    """A certificate with an expiration date in the past must be set to expired;
    within 30 days must be expiring_soon."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Marcus Vance", role="user")
    db_session.add(crew)
    await db_session.commit()

    past_date = date.today() - timedelta(days=10)
    expired_data = {
        "certificate_type": "STCW",
        "expiry_date": past_date.isoformat(),
    }
    expired_document_id = str(uuid.uuid4())
    await _add_extracted_certificate_document(db_session, crew.id, expired_document_id)
    cert_expired = await certification_service.link_extracted_certificate(
        crew_id=crew.id, document_id=expired_document_id, extracted_data=expired_data
    )
    assert cert_expired is not None
    assert cert_expired.status == "expired"

    soon_date = date.today() + timedelta(days=15)
    soon_data = {
        "certificate_type": "FOET",
        "expiry_date": soon_date.isoformat(),
    }
    soon_document_id = str(uuid.uuid4())
    await _add_extracted_certificate_document(db_session, crew.id, soon_document_id)
    cert_soon = await certification_service.link_extracted_certificate(
        crew_id=crew.id, document_id=soon_document_id, extracted_data=soon_data
    )
    assert cert_soon is not None
    assert cert_soon.status == "expiring_soon"


@pytest.mark.asyncio
async def test_extraction_service_accepts_cert_alias_without_value_error():
    """Calling extract_document with document_type='cert' must normalize to 'certificate'
    and not raise ValueError."""
    with patch.object(extraction_service, "parse_response", return_value={"mock": True}):
        with patch("app.services.ollama.ollama_client.extract", new=AsyncMock(return_value={})):
            result = await extraction_service.extract_document("Some cert text", "cert")
            assert result == {"mock": True}


@pytest.mark.asyncio
async def test_document_service_process_document_links_certificate(db_session):
    """End-to-end integration: DocumentService.process_document for a certificate
    document creates and links the Certification row."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Lars Nygard", role="user")
    db_session.add(crew)
    await db_session.flush()

    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="bosiet_cert.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="/tmp/fake_cert.pdf",
        storage_type="local",
        classification="cert",  # Uses the frontend alias
        extraction_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()

    mock_llm_result = {
        "document_type": "certificate",
        "certificate_type": "BOSIET",
        "certificate_number": "RN-443322",
        "issuing_body": "Falck Safety",
        "expiry_date": (date.today() + timedelta(days=400)).isoformat(),
        "confidence": {"certificate_type": 0.95},
    }

    with patch(
        "app.services.text_extraction.text_extraction_service.extract_text",
        new=AsyncMock(return_value="Fake Text"),
    ):
        with patch.object(
            extraction_service, "extract_document", new=AsyncMock(return_value=mock_llm_result)
        ):
            result = await document_service.process_document(doc.id)

    assert result["status"] == "extracted"

    # Verify Certification row was auto-created and linked to this document
    stmt = select(Certification).where(Certification.crew_member_id == crew.id)
    certs = (await db_session.execute(stmt)).scalars().all()
    assert len(certs) == 1
    assert certs[0].cert_type == "BOSIET"
    assert certs[0].document_ref == doc.id
    assert certs[0].cert_number == "RN-443322"
    assert certs[0].issuing_body == "Falck Safety"


@pytest.mark.asyncio
async def test_document_service_does_not_link_low_confidence_certificate(db_session):
    """Review-gated certificate data must not mutate canonical certifications."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Review Needed", role="user")
    db_session.add(crew)
    await db_session.flush()

    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="uncertain_cert.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="/tmp/uncertain_cert.pdf",
        storage_type="local",
        classification="certificate",
        extraction_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()

    extraction_result = {
        "document_type": "certificate",
        "certificate_type": "BOSIET",
        "confidence": {"certificate_type": 0.4},
    }

    with patch(
        "app.services.text_extraction.text_extraction_service.extract_text",
        new=AsyncMock(return_value="Fake Text"),
    ):
        with patch.object(
            extraction_service, "extract_document", new=AsyncMock(return_value=extraction_result)
        ):
            result = await document_service.process_document(doc.id)

    assert result["status"] == "needs_review"
    stmt = select(Certification).where(Certification.crew_member_id == crew.id)
    assert (await db_session.execute(stmt)).scalars().all() == []


@pytest.mark.asyncio
async def test_reprocessing_approved_document_without_evidence_reopens_review(db_session):
    """Legacy approved rows must not auto-publish newly extracted evidence."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Legacy Approved", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="legacy-approved.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="/tmp/legacy-approved.pdf",
        storage_type="local",
        classification="certificate",
        extraction_status="approved",
        extracted_data=None,
    )
    db_session.add(doc)
    await db_session.commit()

    extraction_result = {
        "document_type": "certificate",
        "certificate_type": "BOSIET",
        "confidence": {"certificate_type": 0.95},
    }
    with (
        patch(
            "app.services.text_extraction.text_extraction_service.extract_text",
            new=AsyncMock(return_value="Fake Text"),
        ),
        patch.object(
            extraction_service, "extract_document", new=AsyncMock(return_value=extraction_result)
        ),
    ):
        result = await document_service.process_document(doc.id)

    assert result["status"] == "needs_review"
    await db_session.refresh(doc)
    assert doc.extraction_status == "needs_review"


@pytest.mark.asyncio
async def test_unclassified_image_certificate_is_persisted_and_linked(db_session):
    """The image default classification must survive extraction and linking."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Image Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="certificate.png",
        file_type="image/png",
        file_size=1024,
        storage_path="/tmp/certificate.png",
        storage_type="local",
        classification=None,
        extraction_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()

    extraction_result = {
        "document_type": "certificate",
        "certificate_type": "STCW",
        "confidence": {"certificate_type": 0.95},
    }
    with (
        patch.object(
            text_extraction_service,
            "is_image",
            return_value=True,
        ),
        patch.object(
            extraction_service,
            "extract_from_image",
            new=AsyncMock(return_value=extraction_result),
        ),
    ):
        result = await document_service.process_document(doc.id)

    assert result["status"] == "extracted"
    await db_session.refresh(doc)
    assert doc.classification == "certificate"
    stmt = select(Certification).where(Certification.crew_member_id == crew.id)
    certs = (await db_session.execute(stmt)).scalars().all()
    assert len(certs) == 1
    assert certs[0].cert_type == "STCW"


@pytest.mark.asyncio
async def test_resume_alias_uses_deterministic_cv_extraction(db_session):
    """Async extraction must normalize CV aliases before choosing a pipeline."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="CV Alias Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="resume.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="/tmp/resume.pdf",
        storage_type="local",
        classification="resume",
        extraction_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()

    cv_result = {"full_name": "CV Alias Crew", "confidence": {"full_name": 0.95}}
    with (
        patch(
            "app.services.text_extraction.text_extraction_service.extract_text",
            new=AsyncMock(return_value="CV text"),
        ),
        patch(
            "app.services.cv_processing.CVProcessingService.extract_cv_deterministically",
            return_value=cv_result,
        ) as deterministic,
        patch.object(extraction_service, "extract_document", new=AsyncMock()) as llm_extract,
    ):
        result = await document_service.process_document(doc.id)

    assert result["status"] == "awaiting_review"
    deterministic.assert_called_once()
    llm_extract.assert_not_awaited()
    await db_session.refresh(doc)
    assert doc.classification == "cv"
    review = (
        await db_session.execute(select(CVReview).where(CVReview.document_id == doc.id))
    ).scalar_one()
    assert review.status == "awaiting_review"
    assert review.proposed_data == cv_result


@pytest.mark.asyncio
async def test_processing_does_not_overwrite_terminal_review_decision(db_session):
    """A late extraction worker must leave approved documents untouched."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Reviewed Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="reviewed.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="/tmp/reviewed.pdf",
        storage_type="local",
        classification="certificate",
        extraction_status="approved",
        extracted_data={"certificate_type": "BOSIET"},
    )
    db_session.add(doc)
    await db_session.commit()

    with patch.object(extraction_service, "extract_document", new=AsyncMock()) as extractor:
        result = await document_service.process_document(doc.id)

    assert result["status"] == "approved"
    extractor.assert_not_awaited()


@pytest.mark.asyncio
async def test_extraction_failure_does_not_overwrite_terminal_review_decision(db_session):
    """A late extractor exception must preserve a concurrent human rejection."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Failed Worker Crew", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="failed.pdf",
        file_type="pdf",
        file_size=10,
        storage_path="/tmp/failed.pdf",
        storage_type="local",
        classification="certificate",
        extraction_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()

    async def fail_after_rejection(*_args, **_kwargs):
        async with get_session_factory()() as session:
            current = await session.get(Document, doc.id)
            assert current is not None
            current.extraction_status = "rejected"
            await session.commit()
        raise RuntimeError("extractor failed after review")

    with patch(
        "app.services.text_extraction.text_extraction_service.extract_text",
        new=fail_after_rejection,
    ):
        result = await document_service.process_document(doc.id)

    assert result["status"] == "rejected"
    await db_session.refresh(doc)
    assert doc.extraction_status == "rejected"
