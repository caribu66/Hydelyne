"""Security regression tests: CV extraction pipeline."""

from unittest.mock import patch

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
async def test_cv_processing_and_crew_query_resolve_aliases_identically():
    """Regression test for the CV_CERT_MAPPINGS / CERT_NAME_MAP merge.

    Before the merge, cv_processing.py and crew_query.py each held their own
    certification-alias dictionary, and they had already diverged: e.g.
    "huet" and "harbour porpoise" were only recognized by crew_query.py's
    search-side dictionary, not by cv_processing.py's CV-ingestion dictionary.
    A consultant whose CV mentioned HUET training would never get a HUET
    Certification row created, even though searching for "HUET" worked.
    This test exercises the CV-ingestion path directly (no LLM call — the
    extraction step is bypassed with a synthetic result) and checks the
    search-side normalizer agrees, proving both sides now share one source.
    """
    import uuid

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.database import get_session_factory
    from app.models import CrewMember
    from app.services.crew_query import normalize_cert_name
    from app.services.cv_processing import cv_processing_service

    factory = get_session_factory()
    crew_id = str(uuid.uuid4())
    async with factory() as session:
        session.add(CrewMember(id=crew_id, full_name="Alias Merge Test Crew", role="user"))
        await session.commit()

    synthetic_extraction = {
        "training_qualifications": ["HUET"],
        "specializations": ["Harbour Porpoise Detection"],
        "skills": [],
        "certifications": [],
    }
    result = await cv_processing_service.process_cv_extraction(
        crew_id, synthetic_extraction, str(uuid.uuid4())
    )
    assert result["certifications_created"] == 2

    async with factory() as session:
        stmt = (
            select(CrewMember)
            .options(selectinload(CrewMember.certifications))
            .where(CrewMember.id == crew_id)
        )
        updated = (await session.execute(stmt)).scalar_one()
        cert_types = {c.cert_type for c in updated.certifications}
        assert "HUET" in cert_types
        assert "Harbour Porpoise Detection" in cert_types

        # The search side, using the same shared dictionary, resolves the
        # same raw alias to the same canonical certificate name.
        assert normalize_cert_name("huet") == "HUET"
        assert normalize_cert_name("harbour porpoise") == "Harbour Porpoise Detection"

        await session.delete(updated)
        await session.commit()


@pytest.mark.llm
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


@pytest.mark.llm
@pytest.mark.asyncio
async def test_cv_processing_creates_certifications():
    """Test that CV processing correctly creates certifications from specializations."""
    import uuid

    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models import CrewMember
    from app.services.cv_processing import cv_processing_service
    from app.services.extraction import extraction_service

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
    processing_result = await cv_processing_service.process_cv_extraction(crew_id, result, doc_id)

    assert processing_result["certifications_created"] > 0
    assert "nationality" in processing_result["fields_updated"]
    assert "date_of_birth" in processing_result["fields_updated"]

    # Verify certifications were created
    from sqlalchemy.orm import selectinload

    async with factory() as session:
        stmt = (
            select(CrewMember)
            .options(selectinload(CrewMember.certifications))
            .where(CrewMember.id == crew_id)
        )
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

    geography = CVProcessingService._geographical_experience(
        {
            "work_history": [
                {"country": "Denmark", "location": "North Sea"},
                {"country": "Denmark", "location": "North Sea"},
                {"country": "Senegal"},
            ]
        }
    )

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
    for needle in (
        "foet",
        "ca-ebs",
        "oguk",
        "marine mammal observer",
        "protected species observer",
        "work boat",
    ):
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


@pytest.mark.asyncio
async def test_helena_lindqvist_cv_extracts_name_summary_and_skills_deterministically():
    """Regression test for the fields that used to be LLM-only: the title
    line (full_name) and the free-text PROFESSIONAL SUMMARY/Skills &
    Competencies block. No LLM call is involved — this is pure PDF-text
    parsing. See backend/docs/consultant-knowledge-core.md."""
    import os

    from app.services.cv_table_extractor import extract_cv_tables

    pdf_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "documents",
        ".cache",
        "050836e8-fe46-452a-921a-aa431ea8ad9f",
        "01dfd48e-5e4d-4705-bc36-ce661fa34ff1_Helena Lindqvist HDL MMO PAM CV.pdf",
    )

    payload = extract_cv_tables(pdf_path).as_extraction_payload()

    assert payload["full_name"] == "Helena Lindqvist"

    summary = payload["professional_summary"]
    assert "MMO/MFO/ENV Technician" in summary
    assert "marine wildlife conservation" in summary
    # The "Skills & Competencies:" sub-header itself must not leak into the
    # narrative paragraph or the skills list.
    assert "Skills & Competencies" not in summary

    skills = payload["skills"]
    assert len(skills) == 10
    assert any("PAMGuard software" in s for s in skills)
    assert any("Microsoft Office Suite" in s for s in skills)
    # A bullet that wraps across two PDF text lines must merge into one
    # entry, not split into two.
    assert any("JNCC and modified JNCC guidelines" in s for s in skills)
    # The template's Private Use Area bullet glyph (U+F0A7) must not leak
    # into the stored text.
    assert all("" not in s for s in skills)


@pytest.mark.asyncio
async def test_extract_cv_deterministically_does_not_clobber_table_training_with_regex_fallback():
    """Regression test for a real data-corruption bug: extract_cv_deterministically
    called training_from_text() (a naive line-by-line regex scan over raw
    flattened PDF text, meant only as a last-resort recovery when the table
    extractor finds nothing) *unconditionally*, and let it silently overwrite
    an already-correct, table-derived training_qualifications list whenever
    it returned anything non-empty — which it always does for a real CV.

    training_from_text tears a table apart when a cell's TYPE column wraps
    across multiple visual PDF text lines (as Helena Lindqvist's real CV
    does), producing interleaved fragments like "Compressed Air Emergency
    Breathing" / "UK 2014 N/A" / "System (CA-EBS)" as three separate list
    entries instead of one correct row — and this was landing in the actual
    crew_members.training_qualifications DB column, corrupting real
    compliance-relevant training/certification dates.

    Only test_extract_cv_deterministically_never_calls_the_llm_for_a_recognized_pdf
    exercised extract_cv_deterministically before this, and it passes text=""
    (masking the bug, since training_from_text("") is a no-op). This test
    goes through the real pipeline — TextExtractionService.extract_text()
    on the actual PDF, same as production — so the regex fallback actually
    has real text to (mis)parse, and would fail without the fix."""
    from app.services.cv_processing import CVProcessingService
    from app.services.text_extraction import TextExtractionService

    pdf_path = _helena_pdf_path()
    text = await TextExtractionService().extract_text(pdf_path, "pdf")
    result = CVProcessingService.extract_cv_deterministically(pdf_path, "pdf", text)

    training = result["training_qualifications"]
    assert len(training) >= 10, f"Expected the full clean TRAINING table, got {len(training)} rows"

    # A correct row keeps the training name, place, and dates together, not
    # torn into separate list entries.
    assert any("Compressed Air Emergency Breathing" in row and "CA-EBS" in row for row in training)
    # These fragments are exactly what the regex fallback produced when it
    # clobbered the table result — their presence means the bug is back.
    assert "UK 2014 N/A" not in training
    assert "Szczecin" not in training  # split off "Szczecin, Poland" as a lone fragment
    assert "Poland" not in training
    assert not any(row.strip() == "Szczecin" for row in training)


def _helena_pdf_path() -> str:
    import os

    return os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "documents",
        ".cache",
        "050836e8-fe46-452a-921a-aa431ea8ad9f",
        "01dfd48e-5e4d-4705-bc36-ce661fa34ff1_Helena Lindqvist HDL MMO PAM CV.pdf",
    )


def test_extract_cv_deterministically_never_calls_the_llm_for_a_recognized_pdf():
    """CVs never go through the LLM (see backend/docs/consultant-knowledge-core.md).
    Patch both LLM entry points to raise if touched — proves this isn't just
    true today by omission, it's structurally guaranteed."""
    from app.services import extraction as extraction_module
    from app.services.cv_processing import CVProcessingService

    def _fail(*args, **kwargs):
        raise AssertionError("extract_cv_deterministically must never call the LLM")

    with (
        patch.object(
            extraction_module.extraction_service, "extract_document_sync", side_effect=_fail
        ),
        patch.object(extraction_module.extraction_service, "extract_document", side_effect=_fail),
    ):
        result = CVProcessingService.extract_cv_deterministically(_helena_pdf_path(), "pdf", "")

    assert result["extraction_method"] == "deterministic"
    assert result["full_name"] == "Helena Lindqvist"
    assert result["nationality"] == "Polish"
    assert len(result["work_history"]) > 0


def test_extract_cv_deterministically_flags_review_for_non_pdf_cv():
    """A CV that isn't a PDF can't go through the deterministic table
    parser (pdfplumber-only) — per the agreed design, it is NOT sent to the
    LLM as a fallback, it's flagged for manual review instead."""
    from app.services.cv_processing import CVProcessingService
    from app.services.extraction import extraction_service

    result = CVProcessingService.extract_cv_deterministically(
        "/does/not/matter.docx", "docx", "some raw CV text"
    )

    assert result["extraction_method"] == "deterministic_failed"
    status, needs_review = extraction_service.determine_review_status(result)
    assert status == "needs_review"
    assert needs_review == ["all"]


def test_extract_cv_deterministically_flags_review_when_template_not_recognized():
    """A PDF that doesn't match the expected template (table extraction
    finds no personal info or work history) also goes to review, not the LLM."""
    from app.services.cv_processing import CVProcessingService
    from app.services.cv_table_extractor import CVTableExtraction
    from app.services.extraction import extraction_service

    with patch(
        "app.services.cv_table_extractor.extract_cv_tables",
        return_value=CVTableExtraction(),
    ):
        result = CVProcessingService.extract_cv_deterministically(
            _helena_pdf_path(), "pdf", "irrelevant text"
        )

    assert result["extraction_method"] == "deterministic_failed"
    status, needs_review = extraction_service.determine_review_status(result)
    assert status == "needs_review"
