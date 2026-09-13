"""Regression tests for untrusted extraction response boundaries."""

import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("value", [None, [], {}, 123])
def test_classification_from_model_result_falls_back_for_non_scalar_values(value):
    from app.services.extraction import ExtractionService

    assert ExtractionService.classification_from_result({"classification": value}) == "other"


def test_classification_from_model_result_preserves_strings():
    from app.services.extraction import ExtractionService

    assert (
        ExtractionService.classification_from_result({"classification": "certificate"})
        == "certificate"
    )


def test_extraction_payload_discards_unknown_and_unbounded_model_fields():
    from app.services.extraction import ExtractionService

    result = ExtractionService.parse_response(
        {
            "response": (
                '{"full_name":"'
                + ("A" * 20_000)
                + '","unexpected":"do not persist","skills":['
                + ','.join('"skill"' for _ in range(150))
                + '],"confidence":{"full_name":0.9}}'
            )
        }
    )

    assert len(result["full_name"]) == 10_000
    assert "unexpected" not in result
    assert len(result["skills"]) == 100


@pytest.mark.parametrize("value", [None, [], "high", 0.9])
def test_confidence_from_model_result_falls_back_to_empty_mapping(value):
    from app.services.extraction import ExtractionService

    assert ExtractionService.confidence_from_result({"confidence": value}) == {}


def test_confidence_from_model_result_preserves_mapping():
    from app.services.extraction import ExtractionService

    assert ExtractionService.confidence_from_result({"confidence": {"name": 0.9}}) == {
        "name": 0.9
    }


def test_extracted_text_is_bounded_before_persistence():
    from app.services.text_extraction import MAX_EXTRACTED_TEXT_CHARS, TextExtractionService

    value = "x" * (MAX_EXTRACTED_TEXT_CHARS + 1_000)

    assert TextExtractionService._bounded_text(value) == value[:MAX_EXTRACTED_TEXT_CHARS]


@pytest.mark.asyncio
async def test_email_extraction_reads_only_the_bounded_prefix(tmp_path):
    from app.services.text_extraction import MAX_EXTRACTED_TEXT_CHARS, TextExtractionService

    path = tmp_path / "oversized.eml"
    path.write_text("x" * (MAX_EXTRACTED_TEXT_CHARS + 10_000), encoding="utf-8")

    result = await TextExtractionService().extract_text(str(path), "eml")

    assert result == "x" * MAX_EXTRACTED_TEXT_CHARS


def test_sync_email_extraction_reads_only_the_bounded_prefix(tmp_path):
    from app.services.text_extraction import MAX_EXTRACTED_TEXT_CHARS, TextExtractionService

    path = tmp_path / "oversized.eml"
    path.write_text("x" * (MAX_EXTRACTED_TEXT_CHARS + 10_000), encoding="utf-8")

    result = TextExtractionService().extract_text_sync(str(path), "eml")

    assert result == "x" * MAX_EXTRACTED_TEXT_CHARS


def test_pdf_text_extraction_rejects_extreme_page_counts(monkeypatch, tmp_path):
    from app.domain.input_limits import MAX_PDF_PAGES
    from app.services.text_extraction import TextExtractionService

    class FakePage:
        def extract_text(self):
            return "page"

    class FakePdf:
        pages = [FakePage() for _ in range(MAX_PDF_PAGES + 1)]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setitem(sys.modules, "pdfplumber", SimpleNamespace(open=lambda _path: FakePdf()))

    with pytest.raises(ValueError, match="maximum"):
        TextExtractionService().extract_text_sync(str(tmp_path / "large-page-tree.pdf"), "pdf")


def test_cv_table_extraction_rejects_extreme_page_counts(monkeypatch, tmp_path):
    from app.domain.input_limits import MAX_PDF_PAGES
    from app.services.cv_table_extractor import extract_cv_tables

    class FakePage:
        def extract_tables(self):
            return []

        def extract_text(self):
            return ""

    class FakePdf:
        pages = [FakePage() for _ in range(MAX_PDF_PAGES + 1)]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setitem(sys.modules, "pdfplumber", SimpleNamespace(open=lambda _path: FakePdf()))

    with pytest.raises(ValueError, match="maximum"):
        extract_cv_tables(str(tmp_path / "large-page-tree.pdf"))


@pytest.mark.parametrize(
    ("file_name", "content", "expected_valid"),
    [
        ("document.pdf", b"not a pdf", False),
        ("document.pdf", b"%PDF-1.7\n", True),
        ("message.msg", b"\xd0\xcf\x11\xe0", False),
    ],
)
def test_downloaded_document_content_is_validated_against_filename(
    file_name, content, expected_valid
):
    from app.services.upload import document_upload_service

    valid, _ = document_upload_service.validate_file_content(file_name, content)

    assert valid is expected_valid


def test_downloaded_document_size_is_bounded():
    from app.services.upload import MAX_FILE_SIZE, document_upload_service

    valid, message = document_upload_service.validate_file_content(
        "document.pdf", b"%PDF-1.7\n" + b"x" * MAX_FILE_SIZE
    )

    assert valid is False
    assert "exceeds maximum size" in message


@pytest.mark.asyncio
async def test_legacy_doc_is_rejected_by_async_and_sync_extractors():
    from app.services.text_extraction import TextExtractionService

    service = TextExtractionService()

    with pytest.raises(ValueError, match="Unsupported file type: doc"):
        await service.extract_text("/does/not/exist.doc", "doc")

    with pytest.raises(ValueError, match="Unsupported file type: doc"):
        service.extract_text_sync("/does/not/exist.doc", "doc")


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_parse_response_rejects_non_standard_json_numbers(constant):
    from app.services.extraction import ExtractionService

    result = ExtractionService.parse_response(
        {"response": '{"confidence": {"overall": ' + constant + "}}"}
    )

    assert result == {
        "error": "Invalid JSON from LLM",
        "needs_review": ["all"],
    }
    assert "raw_response" not in result
