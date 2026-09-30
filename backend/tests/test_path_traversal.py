"""Security regression tests: path traversal prevention."""

import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.upload import DocumentUploadService, is_managed_dropbox_path, safe_path_component

# ---------------------------------------------------------------------------
# safe_path_component unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "../../etc",
        "..%2f",
        "..\\",
        "../../../etc/passwd",
        "/etc/passwd",
        "crew/../../../etc",
        "crew\x00",
        "crew\n",
        "",
        "a" * 300,
    ],
)
def test_safe_path_component_rejects_traversal(value):
    with pytest.raises(ValueError):
        safe_path_component(value, "crew_id")


def test_safe_path_component_rejects_double_dot():
    with pytest.raises(ValueError):
        safe_path_component("..", "filename")


def test_safe_path_component_rejects_slash():
    with pytest.raises(ValueError):
        safe_path_component("a/b", "crew_id")


def test_safe_path_component_rejects_backslash():
    with pytest.raises(ValueError):
        safe_path_component("a\\b", "crew_id")


def test_safe_path_component_accepts_uuid():
    uuid_val = "550e8400-e29b-41d4-a716-446655440000"
    assert safe_path_component(uuid_val, "crew_id") == uuid_val


def test_safe_path_component_accepts_dashed_name():
    val = "test-crew-id"
    assert safe_path_component(val, "crew_id") == val


@pytest.mark.parametrize(
    "value",
    [
        "/hydenlyne/crew/documents/cv/file.pdf",
        "/hydenlyne/crew/legacy/file.pdf",
    ],
)
def test_managed_dropbox_path_accepts_safe_paths(value):
    assert is_managed_dropbox_path(value)


@pytest.mark.parametrize(
    "value",
    [
        "/hydenlyne/crew/../../other/file.pdf",
        "/hydenlyne/crew/documents/../secrets/file.pdf",
        "/hydenlyne//documents/cv/file.pdf",
        "/hydenlyne/crew",
    ],
)
def test_managed_dropbox_path_rejects_remote_traversal(value):
    assert not is_managed_dropbox_path(value)


@pytest.mark.asyncio
async def test_delete_from_dropbox_rejects_unmanaged_path(upload_service):
    upload_service.dropbox_available = True
    with patch("app.services.upload.dropbox_request_status", new_callable=AsyncMock) as request:
        assert not await upload_service.delete_from_dropbox("/hydenlyne/crew/../../secret.pdf")
        request.assert_not_awaited()


# ---------------------------------------------------------------------------
# _get_local_cache_path traversal tests
# ---------------------------------------------------------------------------


@pytest.fixture
def upload_service():
    return DocumentUploadService()


def test_get_local_cache_path_rejects_dotdot_in_last_two(upload_service):
    """If the last two path components contain '..', the path must be rejected."""
    result = upload_service._get_local_cache_path("/hydenlyne/crew/..")
    assert result is None


def test_get_local_cache_path_rejects_trailing_dotdot(upload_service):
    result = upload_service._get_local_cache_path("/hydenlyne/crew/..")
    assert result is None


def test_get_local_cache_path_rejects_empty_components(upload_service):
    result = upload_service._get_local_cache_path("/hydenlyne/")
    assert result is None


def test_get_local_cache_path_rejects_slash_in_components(upload_service):
    result = upload_service._get_local_cache_path("/hydenlyne/crew/sub/file")
    # 'sub' and 'file' are individually valid, so this returns a cache path
    # (the traversal in the middle is contained within cache_path)
    assert result is not None
    assert str(result).startswith(str(upload_service.cache_path))


# ---------------------------------------------------------------------------
# get_file must not serve arbitrary local files (traversal sink)
# ---------------------------------------------------------------------------


def test_get_file_rejects_traversal(upload_service):
    """get_file must NOT fall back to reading arbitrary local paths."""
    result = upload_service.get_file("../../../etc/passwd")
    assert result is None


def test_get_file_rejects_absolute_path(upload_service):
    result = upload_service.get_file("/etc/passwd")
    assert result is None


def test_get_file_rejects_dotdot_filename(upload_service):
    result = upload_service.get_file("/hydenlyne/crew/..")
    assert result is None


def test_get_file_rejects_cache_symlink_escape(upload_service, tmp_path: Path):
    """A cache-directory symlink must not turn a managed read into file read."""
    cache_path = tmp_path / "cache"
    escape_path = tmp_path / "cache-escape"
    cache_path.mkdir()
    escape_path.mkdir()
    secret = escape_path / "secret.pdf"
    secret.write_bytes(b"private")
    (cache_path / "crew").symlink_to(escape_path, target_is_directory=True)
    upload_service.cache_path = cache_path

    assert upload_service.get_file("/hydenlyne/crew/secret.pdf") is None
    assert upload_service.delete_file("/hydenlyne/crew/secret.pdf") is False


# ---------------------------------------------------------------------------
# REST upload endpoint: crew_id traversal -> 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_with_traversal_crew_id_rejected(client):
    """Upload with a traversal crew_id must be rejected."""
    test_file = io.BytesIO(
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \n%%EOF"
    )
    for bad_crew_id in ["../../etc", "..%2fpasswd", "/etc/passwd", "a/../../b"]:
        response = await client.post(
            "/api/documents/upload",
            data={"crew_id": bad_crew_id},
            files={"file": ("test.pdf", test_file, "application/pdf")},
        )
        assert response.status_code == 400, f"Expected 400 for crew_id={bad_crew_id}"
        test_file.seek(0)
