"""Tests for webhook-driven removal of records deleted inside Dropbox."""

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.api.dropbox import (
    _managed_dropbox_owner_id,
    process_dropbox_deletion,
    process_dropbox_file,
)
from app.database import get_session_factory
from app.models import Certification, CrewMember, CVReview, DocumentRequest, IncomingDocumentReview
from app.models import Document as DocumentModel


def test_managed_dropbox_owner_rejects_login_accounts():
    """Managed Dropbox paths must not attach files to login account rows."""
    account = SimpleNamespace(id="staff-id", password_hash="hashed", role="staff")
    legacy_contractor = SimpleNamespace(id="contractor-id", password_hash=None, role=None)

    assert _managed_dropbox_owner_id(account) is None
    assert _managed_dropbox_owner_id(legacy_contractor) == "contractor-id"


@pytest.mark.asyncio
async def test_dropbox_challenge_is_plain_text(client):
    """Dropbox verification requires the challenge echoed as the body."""
    response = await client.get("/api/dropbox/webhook?challenge=abc123")
    assert response.status_code == 200
    assert response.text == "abc123"
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_dropbox_challenge_is_bounded(client):
    from app.api.dropbox import MAX_DROPBOX_WEBHOOK_CHALLENGE_LENGTH

    response = await client.get(
        "/api/dropbox/webhook?challenge="
        + "x" * (MAX_DROPBOX_WEBHOOK_CHALLENGE_LENGTH + 1)
    )

    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("use_content_length", [True, False])
async def test_dropbox_webhook_body_is_bounded(use_content_length):
    from fastapi import HTTPException

    from app.api.dropbox import (
        MAX_DROPBOX_WEBHOOK_BODY_BYTES,
        _read_bounded_webhook_body,
    )

    class FakeRequest:
        headers = (
            {"content-length": str(MAX_DROPBOX_WEBHOOK_BODY_BYTES + 1)}
            if use_content_length
            else {}
        )

        async def stream(self):
            yield b"x" * (MAX_DROPBOX_WEBHOOK_BODY_BYTES + 1)

    with pytest.raises(HTTPException) as error:
        await _read_bounded_webhook_body(FakeRequest())

    assert error.value.status_code == 413


def test_dropbox_webhook_account_fanout_is_bounded():
    from fastapi import HTTPException

    from app.api.dropbox import (
        MAX_DROPBOX_WEBHOOK_ACCOUNTS,
        _validate_webhook_accounts,
    )

    with pytest.raises(HTTPException) as error:
        _validate_webhook_accounts(["dbid:account"] * (MAX_DROPBOX_WEBHOOK_ACCOUNTS + 1))

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_dropbox_file_outside_managed_root_is_ignored():
    """A connected Dropbox account must not ingest unrelated root files."""
    with patch("app.api.dropbox.get_session_factory") as get_factory:
        await process_dropbox_file(
            {
                ".tag": "file",
                "path_lower": "/personal/passport.pdf",
                "name": "passport.pdf",
            }
        )
        get_factory.assert_not_called()


@pytest.mark.asyncio
async def test_dropbox_deletion_outside_managed_root_is_ignored():
    """Deletion notifications must not mutate rows outside the managed root."""
    with patch("app.api.dropbox.get_session_factory") as get_factory:
        await process_dropbox_deletion("/personal/passport.pdf")
        get_factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entry",
    [
        {
            ".tag": "file",
            "path_lower": "/hydenlyne/crew/documents/cv/file.pdf",
            "name": "file.pdf",
            "size": "100",
        },
        {
            ".tag": "file",
            "path_lower": "/hydenlyne/crew/documents/cv/file.pdf",
            "name": "file.pdf",
            "size": -1,
        },
        {
            ".tag": "file",
            "path_lower": "/hydenlyne/crew/documents/cv/file.pdf",
            "name": "file.pdf",
            "rev": ["unexpected"],
        },
    ],
)
async def test_dropbox_file_with_invalid_metadata_is_ignored(entry):
    """Malformed provider metadata must not reach SQLAlchemy binding."""
    with patch("app.api.dropbox.get_session_factory") as get_factory:
        await process_dropbox_file(entry)
        get_factory.assert_not_called()


async def _make_document(crew_id: str, doc_id: str, dropbox_path: str) -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            CrewMember(
                id=crew_id,
                full_name="Deletion Test Crew",
                email=None,
                phone=None,
                nationality=None,
                role="user",
            )
        )
        session.add(
            DocumentModel(
                id=doc_id,
                crew_member_id=crew_id,
                file_name="deleted.pdf",
                file_type="pdf",
                file_size=1234,
                storage_type="dropbox",
                storage_path=dropbox_path,
                dropbox_path=dropbox_path,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_deletion_removes_document_record(monkeypatch):
    """A file deleted in Dropbox drops the matching row."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    path = f"/hydenlyne/{crew_id}/documents/cv/{doc_id}_deleted.pdf"
    await _make_document(crew_id, doc_id, path)
    mocked_delete_file = MagicMock()
    monkeypatch.setattr("app.api.dropbox.document_upload_service.delete_file", mocked_delete_file)
    with patch(
        "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
        new=AsyncMock(return_value=True),
    ) as reconcile_document_index:
        await process_dropbox_deletion(path)

    # Regression guard: this path once raised NameError because the upload
    # service was referenced without being imported.
    # Cleanup must use values captured before the ORM row is deleted and
    # committed; accessing an expired deleted instance is unsafe in async ORM.
    mocked_delete_file.assert_called_once_with(path)
    reconcile_document_index.assert_awaited_once_with(doc_id)

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_deletion_matches_dropbox_path_lower_for_uppercase_filename():
    """Dropbox sends path_lower while stored display paths retain case."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    stored_path = f"/hydenlyne/{crew_id}/documents/cv/{doc_id}_Uppercase-CV.PDF"
    await _make_document(crew_id, doc_id, stored_path)

    await process_dropbox_deletion(stored_path.lower())

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_deletion_ignores_empty_path():
    """An empty path is a no-op rather than a mass delete."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    path = f"/hydenlyne/{crew_id}/documents/cv/{doc_id}_keep.pdf"
    await _make_document(crew_id, doc_id, path)

    await process_dropbox_deletion("")

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
        assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_deletion_of_unknown_path_is_noop():
    """An unmatched path leaves existing records alone."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    path = f"/hydenlyne/{crew_id}/documents/cv/{doc_id}_present.pdf"
    await _make_document(crew_id, doc_id, path)

    await process_dropbox_deletion("/hydenlyne/nobody/documents/cv/missing.pdf")

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
        assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_deletion_unlinks_certificate_evidence():
    """Deleting source evidence must not leave a dangling document reference."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    path = f"/hydenlyne/{crew_id}/documents/cert/{doc_id}_deleted.pdf"
    await _make_document(crew_id, doc_id, path)

    factory = get_session_factory()
    async with factory() as session:
        session.add(
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew_id,
                cert_type="STCW",
                status="valid",
                verification_status="verified",
                document_ref=doc_id,
            )
        )
        await session.commit()

    await process_dropbox_deletion(path)

    async with factory() as session:
        cert = (
            await session.execute(
                select(Certification).where(Certification.crew_member_id == crew_id)
            )
        ).scalar_one()
        assert cert.document_ref is None
        assert cert.verification_status == "unverified"
        assert cert.status == "pending_verification"


@pytest.mark.asyncio
async def test_revision_invalidates_old_extraction_and_certificate_link(monkeypatch):
    """A changed Dropbox binary must not retain evidence from its old revision."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    path = f"/hydenlyne/{crew_id}/documents/cert/{doc_id}_revised.pdf"
    await _make_document(crew_id, doc_id, path)

    factory = get_session_factory()
    async with factory() as session:
        doc = await session.get(DocumentModel, doc_id)
        assert doc is not None
        doc.dropbox_revision = "old-revision"
        doc.extraction_status = "extracted"
        doc.extracted_data = {"certificate_type": "STCW"}
        doc.extracted_text = "old evidence"
        doc.extraction_confidence = {"certificate_type": 0.99}
        session.add(
            Certification(
                id=str(uuid.uuid4()),
                crew_member_id=crew_id,
                cert_type="STCW",
                status="valid",
                verification_status="verified",
                document_ref=doc_id,
            )
        )
        await session.commit()

    dispatch = MagicMock()
    monkeypatch.setattr("app.api.dropbox.process_dropbox_document.delay", dispatch)
    monkeypatch.setattr("app.api.dropbox.settings.ENABLE_SEMANTIC_SEARCH", True)
    with (
        patch("app.api.dropbox.document_upload_service.delete_file") as delete_file,
        patch("app.api.dropbox.cache_service.delete", new=AsyncMock()) as delete_cache,
        patch(
            "app.services.qdrant.qdrant_service.delete_document",
            new=AsyncMock(side_effect=RuntimeError("qdrant unavailable")),
        ) as delete_embedding,
        patch(
            "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
            new=AsyncMock(side_effect=RuntimeError("meilisearch unavailable")),
        ) as reconcile_document_index,
        patch("app.tasks.document_tasks.cleanup_document_projections.delay") as cleanup,
    ):
        await process_dropbox_file(
            {
                ".tag": "file",
                "path_lower": path,
                "name": "revised.pdf",
                "rev": "new-revision",
                "size": 456,
            }
        )

    delete_file.assert_called_once_with(path)
    assert delete_cache.await_count == 2
    cleanup.assert_called_once_with(doc_id)
    delete_embedding.assert_awaited_once_with(doc_id)
    reconcile_document_index.assert_awaited_once_with(doc_id)
    dispatch.assert_called_once_with(doc_id)

    async with factory() as session:
        doc = await session.get(DocumentModel, doc_id)
        assert doc is not None
        assert doc.extraction_status == "pending"
        assert doc.extracted_data is None
        assert doc.extracted_text is None
        assert doc.extraction_confidence is None
        cert = (
            await session.execute(
                select(Certification).where(Certification.crew_member_id == crew_id)
            )
        ).scalar_one()
        assert cert.document_ref is None
        assert cert.verification_status == "unverified"
        assert cert.status == "pending_verification"


@pytest.mark.asyncio
async def test_contractor_revision_reopens_incoming_review(monkeypatch):
    """A revised approved contractor upload must return to the review queue."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    path = f"/hydenlyne/{crew_id}/documents/cert/{doc_id}_revised.pdf"
    await _make_document(crew_id, doc_id, path)

    factory = get_session_factory()
    async with factory() as session:
        doc = await session.get(DocumentModel, doc_id)
        assert doc is not None
        doc.uploaded_by = "contractor-upload-link"
        doc.classification = "certificate"
        doc.dropbox_revision = "old-revision"
        doc.extraction_status = "approved"
        request = DocumentRequest(
            id=str(uuid.uuid4()),
            crew_member_id=crew_id,
            token_hash=f"revision-{doc_id}",
            expires_at=datetime(2030, 1, 1),
            created_by="admin",
        )
        review = IncomingDocumentReview(
            id=str(uuid.uuid4()),
            request_id=request.id,
            document_id=doc_id,
            status="resolved",
            claimed_by="admin",
            resolved_at=datetime(2026, 9, 1),
        )
        session.add_all([request, review])
        await session.commit()

    monkeypatch.setattr("app.api.dropbox.process_dropbox_document.delay", lambda *_args: None)
    await process_dropbox_file(
        {
            ".tag": "file",
            "path_lower": path,
            "name": "revised.pdf",
            "rev": "new-revision",
            "size": 456,
        }
    )

    async with factory() as session:
        refreshed_review = await session.get(IncomingDocumentReview, review.id)
        assert refreshed_review is not None
        assert refreshed_review.status == "unread"
        assert refreshed_review.claimed_by is None
        assert refreshed_review.resolved_at is None


@pytest.mark.asyncio
async def test_new_dropbox_document_is_retryable_when_dispatch_fails(monkeypatch):
    crew_id = str(uuid.uuid4())
    path = f"/hydenlyne/{crew_id}/documents/other/new.pdf"
    factory = get_session_factory()
    async with factory() as session:
        session.add(CrewMember(id=crew_id, full_name="Dispatch Failure Crew", role="user"))
        await session.commit()

    def fail_dispatch(*_args):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr("app.api.dropbox.process_dropbox_document.delay", fail_dispatch)
    await process_dropbox_file(
        {
            ".tag": "file",
            "path_lower": path,
            "name": "new.pdf",
            "rev": "new-revision",
            "size": 456,
        }
    )

    async with factory() as session:
        doc = (
            await session.execute(select(DocumentModel).where(DocumentModel.dropbox_path == path))
        ).scalar_one()
        assert doc.extraction_status == "failed"


@pytest.mark.asyncio
async def test_cv_revision_reopens_terminal_review(monkeypatch):
    """A revised CV must not short-circuit on its prior approval decision."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    path = f"/hydenlyne/{crew_id}/documents/cv/{doc_id}_revised.pdf"
    await _make_document(crew_id, doc_id, path)

    factory = get_session_factory()
    async with factory() as session:
        doc = await session.get(DocumentModel, doc_id)
        assert doc is not None
        doc.classification = "cv"
        doc.dropbox_revision = "old-revision"
        doc.extraction_status = "approved"
        session.add(
            CVReview(
                document_id=doc_id,
                crew_member_id=crew_id,
                status="approved",
                prior_publication_status="approved",
                proposed_data={"full_name": "Old"},
                approved_data={"full_name": "Old"},
                submitted_by="admin",
                reviewed_by="admin",
                review_note="old decision",
            )
        )
        await session.commit()

    monkeypatch.setattr("app.api.dropbox.process_dropbox_document.delay", lambda *_args: None)
    await process_dropbox_file(
        {
            ".tag": "file",
            "path_lower": path,
            "name": "revised.pdf",
            "rev": "new-revision",
            "size": 456,
        }
    )

    async with factory() as session:
        review = (
            await session.execute(select(CVReview).where(CVReview.document_id == doc_id))
        ).scalar_one()
        assert review.status == "awaiting_review"
        assert review.proposed_data is None
        assert review.approved_data is None
        assert review.reviewed_by is None
        assert review.review_note is None
