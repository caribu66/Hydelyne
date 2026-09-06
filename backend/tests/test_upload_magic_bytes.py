"""Security regression tests: upload magic-byte validation."""

import io

import pytest
import pytest_asyncio

from app.models import CrewMember

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
PDF_SIGNATURE = b"%PDF-1.4\n%test\n"
JPG_SIGNATURE = b"\xff\xd8\xff\xe0\x00\x10JFIF"
DOCX_SIGNATURE = b"PK\x03\x04\x14\x00\x00\x00"


@pytest_asyncio.fixture(autouse=True)
async def existing_upload_crew(db_session):
    """Uploads require a real parent record; foreign-key orphans are rejected."""
    db_session.add(CrewMember(id="test-crew-id", full_name="Magic Byte Test Contractor"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_upload_png_with_wrong_magic_bytes_rejected(client):
    """A .png file whose content doesn't start with the PNG signature must 400."""
    test_file = io.BytesIO(b"This is not a PNG file at all")
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("evil.png", test_file, "image/png")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_pdf_with_valid_magic_bytes_accepted(client):
    """A .pdf file with proper %PDF header must be accepted."""
    test_file = io.BytesIO(PDF_SIGNATURE)
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("valid.pdf", test_file, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "valid.pdf"


@pytest.mark.asyncio
async def test_upload_pdf_with_spaces_in_filename_accepted(client):
    """Display filenames may contain spaces; only the storage key is normalised."""
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("Helena Lindqvist CV.pdf", io.BytesIO(PDF_SIGNATURE), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["file_name"] == "Helena Lindqvist CV.pdf"


@pytest.mark.asyncio
async def test_upload_png_with_valid_magic_bytes_accepted(client):
    """A .png file with proper signature must be accepted."""
    test_file = io.BytesIO(PNG_SIGNATURE)
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("valid.png", test_file, "image/png")},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_jpg_with_valid_magic_bytes_accepted(client):
    """A .jpg file with proper signature must be accepted."""
    test_file = io.BytesIO(JPG_SIGNATURE)
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("valid.jpg", test_file, "image/jpeg")},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_docx_with_wrong_magic_bytes_rejected(client):
    """A .docx file whose content doesn't start with PK signature must 400."""
    test_file = io.BytesIO(b"Not a zip/docx file content")
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={
            "file": (
                "evil.docx",
                test_file,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_exe_rejected_by_extension(client):
    """An .exe file must be rejected by extension check."""
    test_file = io.BytesIO(b"MZ\x90\x00")
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("evil.exe", test_file, "application/x-executable")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_eml_with_rfc5322_headers_accepted(client):
    """Standard RFC 5322 .eml files starting with From: or Date: must be accepted."""
    eml_content = (
        b"From: operations@hydenlyne.com\nTo: crew@example.com\nSubject: Mobilization\n\nDetails"
    )
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("confirmation.eml", io.BytesIO(eml_content), "message/rfc822")},
    )
    assert response.status_code == 200
    assert response.json()["file_name"] == "confirmation.eml"


@pytest.mark.asyncio
async def test_upload_eml_with_invalid_content_rejected(client):
    """An .eml file with binary/invalid headers must be rejected."""
    bad_eml = io.BytesIO(b"MZ\x90\x00not an email")
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": "test-crew-id"},
        files={"file": ("fake.eml", bad_eml, "message/rfc822")},
    )
    assert response.status_code == 400
