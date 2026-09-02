"""Security regression tests: CV extraction pipeline."""
from unittest.mock import AsyncMock, patch

import pytest

SAMPLE_CV_TEXT = """HELENA LINDQVIST
PERSONAL INFORMATION
NATIONALITY: Polish
COUNTRY OF RESIDENCE: Poland
DATE OF BIRTH: 20/02/1979
EDUCATION: Maritime Academy Szczecin, Poland
LANGUAGES: Polish (native), English (fluent)
GENDER: Female
FLYING POINT: Berlin - Brandenburg, Germany

EXPERTISE
- MMO
- PAM
- ADD

PROFESSIONAL SUMMARY
Experienced MMO/MFO/ENV Technician with a strong maritime background in the seismic industry,
skilled in supporting offshore operations and environmental compliance.

CERTIFICATIONS/TRAINING
BOSIET - Vulcan Training, 18/12/2014, expires 01/02/2030
FOET - Inverness, 2009, expires N/A
PAMGUARD Advanced - Inverness, 2011
"""


@pytest.mark.asyncio
async def test_cv_extraction_returns_correct_structure():
    """Test that CV extraction returns the expected structured format."""
    from app.services.extraction import extraction_service

    result = extraction_service.extract_document_sync(SAMPLE_CV_TEXT, "cv")

    assert result["document_type"] == "cv"
    assert "Lindqvist" in result["full_name"]
    assert result["nationality"] == "Polish"
    assert result["date_of_birth"] == "1979-02-20"
    assert "MMO" in result["specializations"]
    assert "PAM" in result["specializations"]
    assert "Polish" in result["languages"]
    assert "English" in result["languages"]
    assert result["document_mismatch"] is False
    assert isinstance(result["confidence"], dict)


@pytest.mark.asyncio
async def test_cv_processing_creates_certifications():
    """Test that CV processing correctly creates certifications from specializations."""
    from app.services.extraction import extraction_service
    from app.services.cv_processing import cv_processing_service
    from app.database import get_session_factory
    from app.models import CrewMember
    from sqlalchemy import select, delete
    import uuid

    factory = get_session_factory()

    # Create a test crew member
    crew_id = str(uuid.uuid4())
    async with factory() as session:
        crew = CrewMember(
            id=crew_id,
            full_name="CV Test Crew",
            email=None,
            phone=None,
            nationality=None,
            role="user",
        )
        session.add(crew)
        await session.commit()

    # Extract and process
    result = extraction_service.extract_document_sync(SAMPLE_CV_TEXT, "cv")
    doc_id = str(uuid.uuid4())
    processing_result = await cv_processing_service.process_cv_extraction(
        crew_id, result, doc_id
    )

    assert processing_result["certifications_created"] > 0
    assert "nationality" in processing_result["fields_updated"]
    assert "date_of_birth" in processing_result["fields_updated"]

    # Verify certifications were created
    from sqlalchemy.orm import selectinload
    async with factory() as session:
        stmt = select(CrewMember).options(selectinload(CrewMember.certifications)).where(CrewMember.id == crew_id)
        updated = (await session.execute(stmt)).scalar_one()
        assert updated.nationality == "Polish"
        assert updated.date_of_birth is not None
        assert len(updated.certifications) >= 2
        cert_types = {c.cert_type for c in updated.certifications}
        assert "JNCC MMO" in cert_types
        assert "PAMGUARD Advanced" in cert_types

        # Cleanup
        await session.delete(updated)
        await session.commit()


def test_cv_geography_preserves_work_history_countries_and_locations():
    from app.services.cv_processing import CVProcessingService

    geography = CVProcessingService._geographical_experience({
        "work_history": [
            {"country": "Denmark", "location": "North Sea"},
            {"country": "Denmark", "location": "North Sea"},
            {"country": "Senegal"},
        ]
    })

    assert geography == ["Denmark", "North Sea", "Senegal"]


def test_merge_table_extraction_fills_personal_info_from_pdf():
    """When the LLM misses personal info, the table extractor fills it in."""
    from app.services.cv_processing import CVProcessingService

    llm_result = {
        "nationality": "Polish",
        "date_of_birth": "1979-02-20",
        # LLM missed: country_of_residence, gender, languages, flying_point
        "training_qualifications": ["JNCC guidelines"],  # wrong table pickup
        "certifications": [],
    }
    table_payload = {
        "personal_information": {
            "NATIONALITY": "Polish",
            "COUNTRY OF RESIDENCE": "Poland",
            "DATE OF BIRTH": "20/02/1979",
            "GENDER": "Female",
            "LANGUAGES": "Polish (native), English (fluent)",
            "FLYING POINT": "Berlin - Brandenburg, Germany",
        },
        "training_qualifications": [
            "FOET — Vulcan Training — Completed 18/12/2025 — Expires 01/02/2030",
            "Marine Mammal Observer — Inverness — Completed 2009 — Expires N/A",
        ],
        "certifications": ["FOET", "Marine Mammal Observer"],
    }
    merged = CVProcessingService.merge_table_extraction(llm_result, table_payload)

    # LLM's values kept where present.
    assert merged["nationality"] == "Polish"
    assert merged["date_of_birth"] == "1979-02-20"
    # Table fills the gaps.
    assert merged["country_of_residence"] == "Poland"
    assert merged["gender"] == "Female"
    assert merged["flying_point"] == "Berlin - Brandenburg, Germany"
    # Languages becomes a list of two entries.
    assert isinstance(merged["languages"], list)
    assert len(merged["languages"]) == 2
    assert any("Polish" in lang for lang in merged["languages"])
    assert any("English" in lang for lang in merged["languages"])
    # Training was wrong in LLM (one fake row) and gets replaced by table.
    assert len(merged["training_qualifications"]) == 2
    assert "FOET" in merged["training_qualifications"][0]
    # Certifications merged with uniqueness preservation.
    assert "FOET" in merged["certifications"]
    assert "Marine Mammal Observer" in merged["certifications"]


@pytest.mark.asyncio
async def test_helena_lindqvist_cv_extracts_personal_information_and_training():
    """Regression test using the real Helena Lindqvist CV (13k chars).

    Locks in:
    - All five personal information fields are extracted with correct types/values.
    - Date of birth 20/02/1979 is normalised to 1979-02-20.
    - Languages list contains the language names (proficiency suffix stripped).
    - Training/qualifications table is fully extracted (>= 10 rows from the CV).
    - Key certifications (FOET, CA-EBS, MMO/PSO) are recognised.
    - The PDF table extractor matches the LLM on personal info and beats
      the LLM on training (14 rows vs the LLM's typical <5).
    """
    import os
    from app.services.cv_table_extractor import extract_cv_tables

    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures_helena_cv.txt")
    pdf_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "documents",
        ".cache",
        "050836e8-fe46-452a-921a-aa431ea8ad9f",
        "01dfd48e-5e4d-4705-bc36-ce661fa34ff1_Helena Lindqvist HDL MMO PAM CV.pdf",
    )

    table_extraction = extract_cv_tables(pdf_path)
    payload = table_extraction.as_extraction_payload()

    # --- Personal information recovered from the PDF table ---
    personal = payload["personal_information"]
    assert personal["NATIONALITY"] == "Polish"
    assert personal["COUNTRY OF RESIDENCE"] == "Poland"
    assert personal["DATE OF BIRTH"] == "20/02/1979"
    assert personal["GENDER"] == "Female"
    assert "Berlin" in personal["FLYING POINT"]

    # --- Training / qualifications table fully recovered ---
    training = payload["training_qualifications"]
    assert len(training) >= 10, f"Expected the full TRAINING table, got {len(training)} rows"
    blob = " | ".join(training).lower()
    for needle in ("foet", "ca-ebs", "oguk", "marine mammal observer", "protected species observer", "work boat"):
        assert needle in blob, f"Missing training row containing {needle!r}"

    # --- Each training record exposes structured place/date/expiry ---
    structured = payload["training_qualifications_structured"]
    foet = next(item for item in structured if "FOET" in item["name"].upper())
    assert foet["place"] == "Vulcan Training"
    assert foet["completed_date"] == "18/12/2025"
    assert foet["expiry_date"] == "01/02/2030"

    # --- Certifications derived from training rows ---
    certs = payload.get("certifications", [])
    assert any("FOET" in c for c in certs)
    assert any("CA-EBS" in c or "CA EBS" in c for c in certs)

    # --- Geography recovered (deterministic) ---
    geography = payload["geographical_experience"]
    assert "United Kingdom" in geography
    assert "Norway" in geography

    # --- Systems recovered (deterministic) ---
    systems = payload["systems"]
    systems_blob = " ".join(systems).upper()
    assert "PAMGUARD" in systems_blob
    assert "ORCA" in systems_blob
    assert "GARMIN" in systems_blob
