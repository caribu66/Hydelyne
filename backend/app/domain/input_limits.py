"""Shared limits for untrusted application inputs."""

MAX_REVIEW_NOTE_LENGTH = 2_000
MAX_PDF_PAGES = 200


def validate_pdf_page_count(page_count: object) -> None:
    """Reject PDFs whose page tree would cause disproportionate parser work."""
    if not isinstance(page_count, int) or isinstance(page_count, bool):
        raise ValueError("PDF page count is invalid")
    if page_count > MAX_PDF_PAGES:
        raise ValueError(f"PDF exceeds maximum of {MAX_PDF_PAGES} pages")


def validate_pagination(limit: object, offset: object, *, maximum: int = 100) -> tuple[int, int]:
    """Validate and clamp pagination values before query construction."""
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    if not isinstance(offset, int) or isinstance(offset, bool):
        raise ValueError("offset must be an integer")
    return min(max(limit, 1), maximum), max(offset, 0)
