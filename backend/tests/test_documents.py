"""Test document upload API."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import CrewMember, Document
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
async def test_upload_document(client, db_session):
    """Test file upload endpoint."""
    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Upload Test Contractor"))
    await db_session.commit()

    # PDF magic bytes + minimal content
    test_file = io.BytesIO(
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    )
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": crew_id},
        files={"file": ("test.pdf", test_file, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "test.pdf"
    assert data["file_type"] == "pdf"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_contractor_upload_link_creates_a_review_queue_item(client, db_session):
    """A bearer link may upload only into its intended contractor review queue."""
    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Requested Upload Contractor"))
    await db_session.commit()

    created = await client.post(
        "/api/documents/requests", data={"crew_id": crew_id, "expires_in_days": "14"}
    )
    assert created.status_code == 200
    token = created.json()["token"]
    assert (await client.get(f"/api/documents/request/{token}")).status_code == 200

    document_id = str(uuid.uuid4())
    with (
        patch("app.api.documents.process_document_extraction.delay", new=MagicMock()),
        patch(
            "app.api.documents.document_upload_service.save_file",
            new=AsyncMock(return_value=(document_id, "/tmp/contractor-document.pdf", 42)),
        ),
    ):
        uploaded = await client.post(
            f"/api/documents/request/{token}/upload",
            data={"idempotency_key": "contractor-retry-1", "classification": "cert"},
            files={
                "file": (
                    "certificate.pdf",
                    io.BytesIO(b"%PDF-1.4\ncontractor\n%%EOF"),
                    "application/pdf",
                )
            },
        )
    assert uploaded.status_code == 200
    assert uploaded.json()["status"] == "pending"
    queue = await client.get("/api/documents/review-queue")
    assert queue.status_code == 200
    assert queue.json()[0]["contractor_name"] == "Requested Upload Contractor"
    assert queue.json()[0]["document_id"] == document_id


@pytest.mark.asyncio
async def test_staff_cannot_create_request_for_another_staff_members_draft(client, db_session, monkeypatch):
    """Staff must not be able to generate upload requests for another staff member's draft."""
    from app.services.crew import auth_service

    owner_id = str(uuid.uuid4())
    other_staff_id = str(uuid.uuid4())
    crew_id = str(uuid.uuid4())

    db_session.add(
        CrewMember(
            id=crew_id,
            full_name="Other Staff Draft",
            publication_status="draft",
            submitted_by=owner_id,
        )
    )
    await db_session.commit()

    # Log in as other staff
    acting_staff = CrewMember(id=other_staff_id, full_name="Acting Staff", role="staff")
    monkeypatch.setattr(auth_service, "get_user_from_token", AsyncMock(return_value=acting_staff))

    response = await client.post(
        "/api/documents/requests", data={"crew_id": crew_id, "expires_in_days": "14"}
    )
    assert response.status_code == 403
    assert "belongs to another user" in response.json()["detail"]


@pytest.mark.asyncio
async def test_contractor_upload_link_rejects_cv_classification(client, db_session):
    """Contractor upload links are for compliance certificates/evidence and must reject CVs."""
    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="CV Reject Contractor"))
    await db_session.commit()

    created = await client.post(
        "/api/documents/requests", data={"crew_id": crew_id, "expires_in_days": "14"}
    )
    assert created.status_code == 200
    token = created.json()["token"]

    uploaded = await client.post(
        f"/api/documents/request/{token}/upload",
        data={"idempotency_key": "contractor-cv-attempt", "classification": "cv"},
        files={
            "file": (
                "resume.pdf",
                io.BytesIO(b"%PDF-1.4\nresume\n%%EOF"),
                "application/pdf",
            )
        },
    )
    assert uploaded.status_code == 403
    assert "CVs must use the staff upload" in uploaded.json()["detail"]


@pytest.mark.asyncio
async def test_contractor_upload_link_idempotency_returns_existing(client, db_session):
    """Duplicate upload with same idempotency key returns the existing document without error."""
    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Idempotency Contractor"))
    await db_session.commit()

    created = await client.post(
        "/api/documents/requests", data={"crew_id": crew_id, "expires_in_days": "14"}
    )
    token = created.json()["token"]

    doc_id = str(uuid.uuid4())
    with (
        patch("app.api.documents.process_document_extraction.delay", new=MagicMock()),
        patch(
            "app.api.documents.document_upload_service.save_file",
            new=AsyncMock(return_value=(doc_id, "/tmp/idempotent.pdf", 50)),
        ),
    ):
        res1 = await client.post(
            f"/api/documents/request/{token}/upload",
            data={"idempotency_key": "retry-key-abc", "classification": "cert"},
            files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")},
        )
        assert res1.status_code == 200
        assert res1.json()["id"] == doc_id

        # Second upload with same key
        res2 = await client.post(
            f"/api/documents/request/{token}/upload",
            data={"idempotency_key": "retry-key-abc", "classification": "cert"},
            files={"file": ("cert.pdf", io.BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")},
        )
        assert res2.status_code == 200
        assert res2.json()["id"] == doc_id


@pytest.mark.asyncio
async def test_staff_review_queue_excludes_other_staff_drafts(client, db_session, monkeypatch):
    """Staff review queue must not reveal incoming documents for other staff members' drafts."""
    from app.services.crew import auth_service
    from app.services.document_requests import document_request_service

    owner_id = str(uuid.uuid4())
    snooping_staff_id = str(uuid.uuid4())
    draft_crew_id = str(uuid.uuid4())
    approved_crew_id = str(uuid.uuid4())

    db_session.add(
        CrewMember(
            id=draft_crew_id,
            full_name="Private Draft Contractor",
            publication_status="draft",
            submitted_by=owner_id,
        )
    )
    db_session.add(
        CrewMember(
            id=approved_crew_id,
            full_name="Approved Public Contractor",
            publication_status="approved",
        )
    )
    await db_session.commit()

    # Owner creates request and document review for their draft
    req1 = await document_request_service.create(
        crew_id=draft_crew_id, actor_id=owner_id, actor_role="staff", expires_in_days=14
    )
    doc1 = Document(
        id=str(uuid.uuid4()),
        crew_member_id=draft_crew_id,
        file_name="private_cert.pdf",
        file_type="pdf",
        file_size=100,
        storage_type="local",
        storage_path="/tmp/doc1.pdf",
    )
    db_session.add(doc1)
    await db_session.commit()
    await document_request_service.create_review(request_id=req1.request_id, document_id=doc1.id)

    # Someone creates request and review for the approved contractor
    req2 = await document_request_service.create(
        crew_id=approved_crew_id, actor_id=owner_id, actor_role="staff", expires_in_days=14
    )
    doc2 = Document(
        id=str(uuid.uuid4()),
        crew_member_id=approved_crew_id,
        file_name="public_cert.pdf",
        file_type="pdf",
        file_size=100,
        storage_type="local",
        storage_path="/tmp/doc2.pdf",
    )
    db_session.add(doc2)
    await db_session.commit()
    await document_request_service.create_review(request_id=req2.request_id, document_id=doc2.id)

    # Now snooping staff views review queue
    snooper = CrewMember(id=snooping_staff_id, full_name="Snooper", role="staff")
    monkeypatch.setattr(auth_service, "get_user_from_token", AsyncMock(return_value=snooper))

    queue_resp = await client.get("/api/documents/review-queue")
    assert queue_resp.status_code == 200
    queue_items = queue_resp.json()
    contractor_names = [item["contractor_name"] for item in queue_items]

    # Must see approved contractor, but MUST NOT see private draft contractor
    assert "Approved Public Contractor" in contractor_names
    assert "Private Draft Contractor" not in contractor_names


@pytest.mark.asyncio
async def test_cv_upload_persists_binary_and_queues_extraction(client, db_session):
    """The CV flow must send bytes before it can be queued for extraction."""
    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="CV Upload Test Contractor"))
    await db_session.commit()

    cv_bytes = b"%PDF-1.4\nCV content that must reach server storage\n%%EOF"
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": crew_id, "classification": "cv"},
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
async def test_cv_upload_records_failed_status_when_worker_dispatch_fails(client, db_session):
    """A broker outage must be visible and must not create another draft."""
    crew_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id,
            full_name="Failed Queue Contractor",
            publication_status="draft",
        )
    )
    await db_session.commit()

    with patch(
        "app.api.documents.process_document_extraction.delay",
        side_effect=RuntimeError("broker unavailable"),
    ):
        response = await client.post(
            "/api/documents/upload",
            data={"crew_id": crew_id, "classification": "cv"},
            files={
                "file": (
                    "failed-queue-cv.pdf",
                    io.BytesIO(b"%PDF-1.4\nqueue failure test\n%%EOF"),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200
    document_id = response.json()["id"]
    assert response.json()["status"] == "failed"
    status = await client.get(f"/api/documents/{document_id}/status")
    assert status.json()["extraction_status"] == "failed"

    deleted = await client.delete(f"/api/documents/{document_id}")
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_cv_upload_retry_reuses_the_original_document(client, db_session):
    """A lost upload response must not create a second CV or review record."""
    crew_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(id=crew_id, full_name="Retry Safe Contractor", publication_status="draft")
    )
    await db_session.commit()
    cv_bytes = b"%PDF-1.4\nretry-safe\n%%EOF"
    form = {"crew_id": crew_id, "classification": "cv", "idempotency_key": "retry-key-1"}

    first = await client.post(
        "/api/documents/upload",
        data=form,
        files={"file": ("retry.pdf", io.BytesIO(cv_bytes), "application/pdf")},
    )
    second = await client.post(
        "/api/documents/upload",
        data=form,
        files={"file": ("retry.pdf", io.BytesIO(cv_bytes), "application/pdf")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    documents = (
        (await db_session.execute(select(Document).where(Document.crew_member_id == crew_id)))
        .scalars()
        .all()
    )
    assert len(documents) == 1
    assert (await client.delete(f"/api/documents/{first.json()['id']}")).status_code == 204


@pytest.mark.asyncio
async def test_cv_upload_idempotency_key_cannot_be_reused_for_another_contractor(
    client, db_session
):
    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    db_session.add_all(
        [
            CrewMember(id=first_id, full_name="First Retry Contractor"),
            CrewMember(id=second_id, full_name="Second Retry Contractor"),
        ]
    )
    await db_session.commit()
    form = {"crew_id": first_id, "classification": "cv", "idempotency_key": "shared-key"}
    file_bytes = b"%PDF-1.4\nshared-key\n%%EOF"
    first = await client.post(
        "/api/documents/upload",
        data=form,
        files={"file": ("first.pdf", io.BytesIO(file_bytes), "application/pdf")},
    )
    conflict = await client.post(
        "/api/documents/upload",
        data={**form, "crew_id": second_id},
        files={"file": ("second.pdf", io.BytesIO(file_bytes), "application/pdf")},
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert (await client.delete(f"/api/documents/{first.json()['id']}")).status_code == 204


@pytest.mark.asyncio
async def test_cv_upload_rejects_malformed_idempotency_key(client, db_session):
    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Key Validation Contractor"))
    await db_session.commit()
    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": crew_id, "classification": "cv", "idempotency_key": "bad key"},
        files={"file": ("invalid-key.pdf", io.BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_staff_cannot_upload_to_another_staff_members_draft(client, db_session, monkeypatch):
    staff = CrewMember(id=str(uuid.uuid4()), full_name="Upload Staff", role="staff")
    other_draft = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Other Staff Draft",
        publication_status="draft",
        submitted_by=str(uuid.uuid4()),
    )
    db_session.add(other_draft)
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )

    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": other_draft.id, "classification": "cv"},
        files={
            "file": (
                "private-draft.pdf",
                io.BytesIO(b"%PDF-1.4\nprivate draft\n%%EOF"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 403


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
