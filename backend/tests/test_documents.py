"""Test document upload API."""
import io

import pytest

from app.services.upload import document_upload_service


@pytest.mark.asyncio
async def test_upload_document(client):
    """Test file upload endpoint."""
    # PDF magic bytes + minimal content
    test_file = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Root 1 0 R >>\n%%EOF")
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
    assert cache_path == document_upload_service.cache_path / "crew-123" / "document-123_candidate.pdf"
