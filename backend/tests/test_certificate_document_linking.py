"""Tests for standalone certificate document ingestion and Certification linking."""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.domain.certifications import normalize_cert_name
from app.domain.fields import normalize_classification
from app.models import Certification, CrewMember, Document
from app.services.crew import certification_service
from app.services.document_service import document_service
from app.services.extraction import extraction_service


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


@pytest.mark.asyncio
async def test_link_extracted_certificate_creates_new_certification(db_session):
    """When a consultant uploads a certificate document, link_extracted_certificate
    must create a new Certification row linked to that document_id."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Sarah Jenkins", role="user")
    db_session.add(crew)
    await db_session.commit()

    doc_id = str(uuid.uuid4())
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
    cert_expired = await certification_service.link_extracted_certificate(
        crew_id=crew.id, document_id=str(uuid.uuid4()), extracted_data=expired_data
    )
    assert cert_expired is not None
    assert cert_expired.status == "expired"

    soon_date = date.today() + timedelta(days=15)
    soon_data = {
        "certificate_type": "FOET",
        "expiry_date": soon_date.isoformat(),
    }
    cert_soon = await certification_service.link_extracted_certificate(
        crew_id=crew.id, document_id=str(uuid.uuid4()), extracted_data=soon_data
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
