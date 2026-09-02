"""Test document upload API."""

import io
from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.services.upload import document_upload_service


def test_embedding_indexing_dispatches_only_when_semantic_search_is_enabled():
    """Phase 3 checkpoint (backend/docs/consultant-knowledge-core.md):
    extraction must queue Qdrant embedding indexing when
    ENABLE_SEMANTIC_SEARCH is on, and must not touch it at all when off —
    the default, so this stays a no-op change for existing deployments."""
    from app.tasks.document_tasks import _maybe_queue_embeddings, index_document_embeddings

    settings = get_settings()
    original = settings.ENABLE_SEMANTIC_SEARCH
    try:
        with patch.object(index_document_embeddings, "delay", new=MagicMock()) as mock_delay:
            settings.ENABLE_SEMANTIC_SEARCH = False
            _maybe_queue_embeddings("doc-1")
            mock_delay.assert_not_called()

            settings.ENABLE_SEMANTIC_SEARCH = True
            _maybe_queue_embeddings("doc-1")
            mock_delay.assert_called_once_with("doc-1")
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = original


@pytest.mark.asyncio
async def test_dispose_engine_lets_a_fresh_engine_be_created_afterward():
    """Regression test for the Celery "attached to a different loop" bug:
    a long-lived worker calling asyncio.run() once per task reuses the
    async engine singleton across tasks, but asyncpg connections are bound
    to the loop that created them. dispose_engine() must drop the
    singleton so the next get_engine() call creates a genuinely new one
    (proven here by object identity, not just a non-crash)."""
    import app.database as app_db

    # Preserve the test suite's engine/session-factory/URL so this test
    # can't leak a dangling reference or a Postgres driver dependency into
    # every other test in the session. get_engine() reads settings.DATABASE_URL,
    # which points at production Postgres — point it at the same sqlite
    # test DB the rest of the suite already uses instead, so the "fresh
    # engine" this test creates doesn't need asyncpg installed.
    original_engine = app_db._engine
    original_session_factory = app_db._session_factory
    original_url = app_db.settings.DATABASE_URL
    try:
        app_db.settings.DATABASE_URL = "sqlite+aiosqlite:///./test.db"
        engine_before = app_db.get_engine()
        await app_db.dispose_engine()
        assert app_db._engine is None
        assert app_db._session_factory is None

        engine_after = app_db.get_engine()
        assert engine_after is not engine_before
    finally:
        await app_db.dispose_engine()
        app_db.settings.DATABASE_URL = original_url
        app_db._engine = original_engine
        app_db._session_factory = original_session_factory


@pytest.mark.asyncio
async def test_preview_cv_extracts_identity_fields_deterministically(client):
    """The Add Specialist modal's CV preview (pre-fills name/nationality
    before a crew record exists) must not call the LLM either — same
    design as the main CV pipeline. Uses the real Helena Lindqvist PDF
    fixture; email/phone are always None because this template never
    carries them."""
    import os

    pdf_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "documents",
        ".cache",
        "050836e8-fe46-452a-921a-aa431ea8ad9f",
        "01dfd48e-5e4d-4705-bc36-ce661fa34ff1_Helena Lindqvist HDL MMO PAM CV.pdf",
    )
    with open(pdf_path, "rb") as f:
        response = await client.post(
            "/api/documents/preview-cv",
            files={"file": ("Helena Lindqvist HDL MMO PAM CV.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Helena Lindqvist"
    assert data["nationality"] == "Polish"
    assert data["email"] is None
    assert data["phone"] is None


@pytest.mark.asyncio
async def test_preview_cv_returns_empty_fields_for_non_pdf(client):
    """A non-PDF CV can't go through the deterministic table parser — per
    the agreed design, this returns empty fields for the operator to fill
    in by hand rather than falling back to the LLM."""
    test_file = io.BytesIO(
        b"PK\x03\x04\x14\x00\x00\x00" + b"not a real docx body but has valid magic bytes"
    )
    response = await client.post(
        "/api/documents/preview-cv",
        files={
            "file": (
                "cv.docx",
                test_file,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {"full_name": None, "email": None, "phone": None, "nationality": None}


@pytest.mark.asyncio
async def test_upload_document(client):
    """Test file upload endpoint."""
    # PDF magic bytes + minimal content
    test_file = io.BytesIO(
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    )
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("test.pdf", test_file, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "test.pdf"
    assert data["file_type"] == "pdf"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_cv_upload_persists_binary_and_queues_extraction(client):
    """The CV flow must send bytes before it can be queued for extraction."""
    cv_bytes = b"%PDF-1.4\nCV content that must reach server storage\n%%EOF"
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id", "classification": "cv"},
        files={"file": ("candidate-cv.pdf", io.BytesIO(cv_bytes), "application/pdf")},
    )

    assert response.status_code == 200
    uploaded = response.json()
    assert uploaded["status"] == "pending"

    status = await client.get(f"/api/documents/{uploaded['id']}/status")
    assert status.status_code == 200
    assert status.json()["classification"] == "cv"
    assert status.json()["extraction_status"] == "pending"

    download = await client.get(f"/api/documents/{uploaded['id']}/download")
    assert download.status_code == 200
    assert download.content == cv_bytes

    deleted = await client.delete(f"/api/documents/{uploaded['id']}")
    assert deleted.status_code == 204
    missing = await client.get(f"/api/documents/{uploaded['id']}/status")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_upload_invalid_file_type(client):
    """Test upload with invalid file type."""
    test_file = io.BytesIO(b"Invalid file content")
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("test.exe", test_file, "application/x-executable")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_document_status_not_found(client):
    """Test document status for non-existent document."""
    response = await client.get("/api/documents/nonexistent-id/status")
    assert response.status_code == 404


def test_dropbox_cache_uses_crew_id_not_classification():
    """A Dropbox path must map to the cache created during upload."""
    cache_path = document_upload_service._get_local_cache_path(
        "/hydenlyne/crew-123/documents/cv/document-123_candidate.pdf"
    )
    assert (
        cache_path == document_upload_service.cache_path / "crew-123" / "document-123_candidate.pdf"
    )
