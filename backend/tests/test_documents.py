"""Test document upload API."""

import io
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import select

from app.api.documents import (
    _content_disposition,
    _lock_active_document_request,
    _parse_optional_form_date,
    _retry_failed_idempotent_document,
    get_document_status,
    list_incoming_document_reviews,
    preview_cv,
)
from app.config import get_settings
from app.database import get_session_factory
from app.models import Certification, CrewMember, Document, IncomingDocumentReview
from app.services.document_requests import _mark_review_resolved, document_request_service
from app.services.upload import CHUNK_SIZE, document_upload_service


class _DocumentSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


def test_resolving_review_records_first_claim_time():
    first_claim = datetime(2026, 9, 13, 12, 0)
    review = SimpleNamespace(
        status="unread",
        claimed_by=None,
        claimed_at=None,
        resolved_at=None,
    )

    _mark_review_resolved(
        review,
        actor_id="staff-1",
        action="approve",
        now=first_claim,
    )
    assert review.claimed_by == "staff-1"
    assert review.claimed_at == first_claim
    assert review.resolved_at == first_claim
    assert review.status == "resolved"

    second_time = datetime(2026, 9, 13, 13, 0)
    _mark_review_resolved(
        review,
        actor_id="staff-2",
        action="reject",
        now=second_time,
    )
    assert review.claimed_at == first_claim
    assert review.resolved_at == second_time
    assert review.status == "rejected"


class _DocumentResult:
    def __init__(self, value, rows=None):
        self.value = value
        self.rows = rows

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.rows or []


@pytest.mark.asyncio
async def test_async_document_worker_rejects_login_account_document(monkeypatch):
    from app.services.document_service import document_service

    document = SimpleNamespace(
        id="document-1",
        crew_member_id="staff-1",
        extraction_status="pending",
        extracted_data=None,
        classification="certificate",
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _DocumentResult(document),
                _DocumentResult(SimpleNamespace(password_hash="hashed", role="staff")),
            ]
        ),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.document_service.get_session_factory",
        lambda: lambda: _DocumentSessionContext(session),
    )
    cleanup = AsyncMock()
    monkeypatch.setattr("app.services.document_service._cleanup_failed_document_projections", cleanup)

    result = await document_service.process_document("document-1")

    assert result == {
        "document_id": "document-1",
        "status": "rejected",
        "classification": "certificate",
    }
    assert document.extraction_status == "rejected"
    session.commit.assert_awaited_once()
    cleanup.assert_awaited_once_with("document-1")
    assert "FOR UPDATE" in str(session.execute.await_args_list[1].args[0])


@pytest.mark.asyncio
async def test_create_document_rejects_login_account_target(monkeypatch):
    from app.services.document_service import document_service

    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=_DocumentResult(
                SimpleNamespace(password_hash="hashed", role="staff")
            )
        ),
        add=MagicMock(),
    )
    monkeypatch.setattr(
        "app.services.document_service.get_session_factory",
        lambda: lambda: _DocumentSessionContext(session),
    )

    with pytest.raises(ValueError, match="Crew member not found"):
        await document_service.create_document(
            "staff-1", "certificate.pdf", "application/pdf", 100, "/tmp/certificate.pdf"
        )

    session.add.assert_not_called()
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_document_status_locks_owner_before_returning_metadata(monkeypatch):
    document = SimpleNamespace(
        id="document-1",
        crew_member_id="crew-1",
        file_name="certificate.pdf",
        extraction_status="approved",
        classification="certificate",
        storage_type="local",
    )
    owner = SimpleNamespace(password_hash=None, role=None, publication_status="approved")
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[_DocumentResult(document), _DocumentResult(owner)]
        )
    )
    monkeypatch.setattr(
        "app.api.documents.get_session_factory",
        lambda: lambda: _DocumentSessionContext(session),
    )

    result = await get_document_status(
        "document-1", Request(scope={"type": "http"}), owner
    )

    assert result["id"] == "document-1"
    assert "FOR UPDATE" in str(session.execute.await_args_list[0].args[0])
    assert "FOR UPDATE" in str(session.execute.await_args_list[1].args[0])


@pytest.mark.asyncio
async def test_review_queue_locks_joined_rows_before_returning_metadata(monkeypatch):
    review = SimpleNamespace(
        id="review-1",
        status="unread",
        claimed_by=None,
        created_at=datetime(2026, 9, 13, 12, 0),
    )
    document = SimpleNamespace(
        id="document-1",
        file_name="certificate.pdf",
        file_type="pdf",
        file_size=10,
        classification="certificate",
        extraction_status="extracted",
    )
    crew = SimpleNamespace(id="crew-1", full_name="Visible Contractor")
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=_DocumentResult(
                None,
                rows=[(review, document, crew)],
            )
        )
    )
    monkeypatch.setattr(
        "app.api.documents.get_session_factory",
        lambda: lambda: _DocumentSessionContext(session),
    )

    result = await list_incoming_document_reviews(SimpleNamespace(id="admin-1", role="admin"))

    assert result[0]["document_id"] == "document-1"
    assert "FOR UPDATE" in str(session.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_review_resolution_locks_contractor_before_review(monkeypatch):
    review = SimpleNamespace(id="review-1", document_id="document-1", status="unread")
    document = SimpleNamespace(
        id="document-1",
        crew_member_id="crew-1",
        extraction_status="processing",
        classification="certificate",
    )
    crew = SimpleNamespace(
        password_hash=None,
        role=None,
        publication_status="approved",
        submitted_by=None,
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _DocumentResult(review),
                _DocumentResult(document),
                _DocumentResult(crew),
                _DocumentResult(review),
            ]
        )
    )
    monkeypatch.setattr(
        "app.services.document_requests.get_session_factory",
        lambda: lambda: _DocumentSessionContext(session),
    )

    with pytest.raises(ValueError, match="not ready for approval"):
        await document_request_service.resolve_review(
            review_id="review-1",
            actor_id="admin-1",
            actor_role="admin",
            action="approve",
        )

    statements = [call.args[0] for call in session.execute.await_args_list]
    assert "FOR UPDATE" not in str(statements[0])
    assert "FOR UPDATE" in str(statements[1])
    assert "FOR UPDATE" in str(statements[2])
    assert "FOR UPDATE" in str(statements[3])


@pytest.mark.asyncio
async def test_reprocess_document_rejects_login_account_target(monkeypatch):
    from app.services.document_service import document_service

    document = SimpleNamespace(id="document-1", crew_member_id="staff-1")
    session = SimpleNamespace(
        execute=AsyncMock(return_value=_DocumentResult(document)),
        get=AsyncMock(return_value=SimpleNamespace(password_hash="hashed", role="staff")),
    )
    monkeypatch.setattr(
        "app.services.document_service.get_session_factory",
        lambda: lambda: _DocumentSessionContext(session),
    )

    with pytest.raises(ValueError, match="Document document-1 not found"):
        await document_service.reprocess_document("document-1")


@pytest.mark.asyncio
async def test_manual_confirmation_rejects_login_account_document(monkeypatch):
    from app.services.document_service import document_service

    document = SimpleNamespace(
        id="document-1",
        crew_member_id="staff-1",
        extraction_status="needs_review",
        classification="certificate",
    )
    account = SimpleNamespace(password_hash="hashed", role="staff")
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[_DocumentResult(document), _DocumentResult(account)]
        ),
    )
    monkeypatch.setattr(
        "app.services.document_service.get_session_factory",
        lambda: lambda: _DocumentSessionContext(session),
    )

    with pytest.raises(ValueError, match="contractor profile"):
        await document_service.confirm_extraction("document-1", {})

    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_manual_matching_locks_target_before_account_check(monkeypatch):
    from app.services.document_service import document_service

    document = SimpleNamespace(id="document-1", crew_member_id=None)
    account = SimpleNamespace(password_hash="hashed", role="staff")
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[_DocumentResult(document), _DocumentResult(account)]
        )
    )
    monkeypatch.setattr(
        "app.services.document_service.get_session_factory",
        lambda: lambda: _DocumentSessionContext(session),
    )

    with pytest.raises(ValueError, match="Crew member not found"):
        await document_service.link_to_crew_member("document-1", "staff-1")

    assert session.execute.await_count == 2
    session_statements = [call.args[0] for call in session.execute.await_args_list]
    assert "FOR UPDATE" in str(session_statements[1])


@pytest.mark.asyncio
async def test_pending_documents_excludes_login_account_rows(monkeypatch):
    from app.services.document_service import document_service

    captured = {}

    class _Session:
        async def execute(self, statement):
            captured["sql"] = str(statement.compile(compile_kwargs={"literal_binds": True}))
            return _DocumentResult(None)

    monkeypatch.setattr(
        "app.services.document_service.get_session_factory",
        lambda: lambda: _DocumentSessionContext(_Session()),
    )

    result = await document_service.get_pending_documents()

    assert result == []
    assert "password_hash IS NULL" in captured["sql"]
    assert "role NOT IN ('staff', 'admin')" in captured["sql"]


def test_document_matching_rejects_login_account_targets():
    """Manual document matching must remain limited to contractor profiles."""
    from app.domain.crew_accounts import is_contractor_profile

    account = SimpleNamespace(password_hash="hashed", role="staff")
    contractor = SimpleNamespace(password_hash=None, role=None)

    assert not is_contractor_profile(account)
    assert is_contractor_profile(contractor)


def test_content_disposition_uses_ascii_fallback_and_encodes_filename_path_chars():
    header = _content_disposition("合同/scan report.pdf")

    assert 'filename="___scan report.pdf"' in header
    assert "filename*=UTF-8''%E5%90%88%E5%90%8C%2Fscan%20report.pdf" in header


@pytest.mark.asyncio
async def test_idempotent_failed_upload_retry_requeues_extraction():
    session = SimpleNamespace(commit=AsyncMock())
    document = SimpleNamespace(id="document-1", extraction_status="failed")

    with patch("app.api.documents.process_document_extraction.delay") as dispatch:
        result = await _retry_failed_idempotent_document(session, document)

    assert document.extraction_status == "pending"
    assert result == "pending"
    dispatch.assert_called_once_with("document-1")
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_idempotent_failed_upload_retry_reports_broker_failure():
    session = SimpleNamespace(
        commit=AsyncMock(),
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalar_one_or_none=lambda: SimpleNamespace(
                    id="document-1", extraction_status="pending"
                )
            )
        ),
    )
    document = SimpleNamespace(id="document-1", extraction_status="failed")

    with patch(
        "app.api.documents.process_document_extraction.delay",
        side_effect=RuntimeError("broker unavailable"),
    ):
        result = await _retry_failed_idempotent_document(session, document)

    assert result == "failed"
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_idempotent_upload_rechecks_revoked_request_before_retry():
    request = SimpleNamespace(status="revoked", expires_at=datetime.now())
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: request)
        ),
        commit=AsyncMock(),
    )

    with pytest.raises(HTTPException, match="invalid or has expired"):
        await _lock_active_document_request(session, "request-1")

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("expiry", [0, -1, 31, True, "14"])
async def test_document_request_service_rejects_invalid_expiry_before_db(expiry):
    with patch("app.services.document_requests.get_session_factory") as get_factory:
        with pytest.raises(ValueError, match="Expiry must be between 1 and 30 days"):
            await document_request_service.create(
                crew_id="crew-1",
                actor_id="staff-1",
                expires_in_days=expiry,
            )
        get_factory.assert_not_called()


@pytest.mark.asyncio
async def test_create_review_query_excludes_login_account_requests():
    """Legacy account-owned request rows must not enter the contractor queue."""

    class EmptyResult:
        def scalar_one_or_none(self):
            return None

    class FakeSession:
        statements = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def execute(self, statement):
            self.statements.append(statement)
            return EmptyResult()

    fake_session = FakeSession()
    with patch(
        "app.services.document_requests.get_session_factory", return_value=lambda: fake_session
    ):
        with pytest.raises(ValueError, match="Document request not found"):
            await document_request_service.create_review(
                request_id="request-1", document_id="document-1"
            )

    sql = str(fake_session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "password_hash IS NULL" in sql
    assert "role NOT IN ('staff', 'admin')" in sql


@pytest.mark.asyncio
async def test_create_review_locks_owner_before_committing_account_review():
    request = SimpleNamespace(
        id="request-1",
        crew_member_id="staff-1",
        status="active",
        expires_at=datetime.now() + timedelta(days=1),
    )
    document = SimpleNamespace(id="document-1", crew_member_id="staff-1")
    account = SimpleNamespace(password_hash="hashed", role="staff")
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _DocumentResult(request),
                _DocumentResult(document),
                _DocumentResult(account),
            ]
        )
    )
    with patch(
        "app.services.document_requests.get_session_factory",
        return_value=lambda: _DocumentSessionContext(session),
    ):
        with pytest.raises(ValueError, match="Contractor not found"):
            await document_request_service.create_review(
                request_id="request-1", document_id="document-1"
            )

    assert "FOR UPDATE" in str(session.execute.await_args_list[2].args[0])


@pytest.mark.asyncio
async def test_extraction_audit_failure_does_not_raise_or_change_outcome():
    from app.services.document_service import _log_extraction_best_effort

    with patch(
        "app.services.audit.audit_service.log_extraction",
        new=AsyncMock(side_effect=RuntimeError("audit unavailable")),
    ) as audit:
        await _log_extraction_best_effort(
            "document-1",
            model_used="llama3.1:8b",
            confidence={},
            status="extracted",
        )

    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirmation_access_audit_failure_does_not_raise():
    from app.services.document_service import _log_access_best_effort

    with patch(
        "app.services.audit.audit_service.log_access",
        new=AsyncMock(side_effect=RuntimeError("audit unavailable")),
    ) as audit:
        await _log_access_best_effort(
            "document-1",
            user_id="system",
            action="confirm_extraction",
            data_keys=["document_type"],
        )

    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_projection_cleanup_queues_search_retry_without_raising():
    from app.services.document_service import _cleanup_failed_document_projections

    with (
        patch(
            "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
            new=AsyncMock(side_effect=RuntimeError("search unavailable")),
        ),
        patch("app.tasks.document_tasks.queue_document_search_reconcile") as queue_search,
    ):
        await _cleanup_failed_document_projections("document-1")

    queue_search.assert_called_once_with("document-1")


@pytest.mark.asyncio
async def test_review_audit_failure_does_not_raise():
    from app.services.document_requests import _log_review_audit_best_effort

    with patch(
        "app.services.audit.audit_service.log_access",
        new=AsyncMock(side_effect=RuntimeError("audit unavailable")),
    ) as audit:
        await _log_review_audit_best_effort(
            document_id="document-1",
            actor_id="admin-1",
            action="review_approve",
            review_id="review-1",
            note="checked",
        )

    audit.assert_awaited_once()


def test_document_upload_metadata_dates_are_parsed_as_iso_dates():
    assert _parse_optional_form_date("2026-09-12", "issue_date") == date(2026, 9, 12)
    assert _parse_optional_form_date("  ", "expiry_date") is None

    with pytest.raises(HTTPException, match="Invalid expiry_date"):
        _parse_optional_form_date("12/09/2026", "expiry_date")


def test_upload_validation_rejects_empty_file():
    from fastapi import UploadFile

    upload = UploadFile(filename="empty.pdf", file=io.BytesIO())
    valid, message = document_upload_service.validate_file(upload, b"")

    assert not valid
    assert message == "File is empty"


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
            _maybe_queue_embeddings("doc-1", "extracted")
            mock_delay.assert_not_called()

            settings.ENABLE_SEMANTIC_SEARCH = True
            for blocked_status in ("failed", "needs_review", "awaiting_review"):
                _maybe_queue_embeddings("doc-1", blocked_status)
            mock_delay.assert_not_called()
            _maybe_queue_embeddings("doc-1", "extracted")
            mock_delay.assert_called_once_with("doc-1")
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = original


def test_document_embedding_text_excludes_c3_extracted_data():
    from app.services.qdrant import document_indexable_text

    document = SimpleNamespace(
        classification="passport",
        file_name="identity.pdf",
        extracted_data={"passport_number": "C3-SECRET"},
    )

    indexable_text = document_indexable_text(document)

    assert indexable_text == "passport document identity.pdf"
    assert "C3-SECRET" not in indexable_text


def test_failed_extraction_result_is_not_acknowledged_as_success():
    from app.tasks.document_tasks import _raise_for_retryable_failure

    with pytest.raises(RuntimeError, match="document extraction failed"):
        _raise_for_retryable_failure({"status": "failed", "error": "provider unavailable"})

    _raise_for_retryable_failure({"status": "failed", "error": "Document not found"})


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
async def test_preview_cv_reads_upload_in_bounded_chunks():
    upload = SimpleNamespace(
        filename="cv.docx",
        read=AsyncMock(side_effect=[b"PK\x03\x04preview", b""]),
    )

    result = await preview_cv(upload, SimpleNamespace())

    assert result == {"full_name": None, "email": None, "phone": None, "nationality": None}
    assert all(call.args == (CHUNK_SIZE,) for call in upload.read.await_args_list)


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

    stored = await db_session.get(Document, data["id"])
    assert stored is not None
    assert stored.classification is None


@pytest.mark.asyncio
async def test_document_audit_log_appends_multiple_events(client, db_session):
    """Audit appends must retain prior events instead of replacing the JSON array."""
    from app.services.audit import audit_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Audit Append Contractor"))
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="audit.pdf",
        file_type="pdf",
        file_size=10,
        storage_type="local",
        storage_path="/tmp/audit.pdf",
    )
    db_session.add(doc)
    await db_session.commit()

    await audit_service.log_access(doc_id, "user-1", "view")
    await audit_service.log_access(doc_id, "user-2", "download")

    await db_session.refresh(doc)
    assert [entry["action"] for entry in doc.access_log or []] == ["view", "download"]


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
async def test_contractor_upload_dispatch_failure_fails_the_review_queue_item(
    client, db_session
):
    """If the broker is down, the committed review row must not linger as
    `unread` in the staff queue for a document marked `failed`."""
    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Dispatch Failure Contractor"))
    await db_session.commit()

    created = await client.post(
        "/api/documents/requests", data={"crew_id": crew_id, "expires_in_days": "14"}
    )
    assert created.status_code == 200
    token = created.json()["token"]

    document_id = str(uuid.uuid4())

    class _BrokerDown:
        def delay(self, *_args, **_kwargs):
            raise ConnectionError("broker down")

    with (
        patch("app.api.documents.process_document_extraction", new=_BrokerDown()),
        patch(
            "app.api.documents.document_upload_service.save_file",
            new=AsyncMock(return_value=(document_id, "/tmp/contractor-failed.pdf", 42)),
        ),
    ):
        uploaded = await client.post(
            f"/api/documents/request/{token}/upload",
            data={"idempotency_key": "contractor-dispatch-fail-1", "classification": "cert"},
            files={
                "file": (
                    "certificate.pdf",
                    io.BytesIO(b"%PDF-1.4\ncontractor\n%%EOF"),
                    "application/pdf",
                )
            },
        )
    assert uploaded.status_code == 200
    assert uploaded.json()["status"] == "failed"

    factory = get_session_factory()
    async with factory() as session:
        doc = (
            await session.execute(select(Document).where(Document.id == document_id))
        ).scalar_one()
        assert doc.extraction_status == "failed"
        review = (
            await session.execute(
                select(IncomingDocumentReview).where(
                    IncomingDocumentReview.document_id == document_id
                )
            )
        ).scalar_one()
        assert review.status == "failed"

    queue = await client.get("/api/documents/review-queue")
    assert queue.status_code == 200
    assert all(item["document_id"] != document_id for item in queue.json())


@pytest.mark.asyncio
async def test_staff_cannot_create_request_for_another_staff_members_draft(
    client, db_session, monkeypatch
):
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
async def test_rejected_contractor_invalidates_existing_upload_link(client, db_session):
    """A link issued before rejection must not remain a bearer upload channel."""
    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Rejected Link Contractor"))
    await db_session.commit()

    created = await client.post("/api/documents/requests", data={"crew_id": crew_id})
    assert created.status_code == 200
    token = created.json()["token"]

    crew = await db_session.get(CrewMember, crew_id)
    assert crew is not None
    crew.publication_status = "rejected"
    await db_session.commit()

    status = await client.get(f"/api/documents/request/{token}")
    assert status.status_code == 404


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
async def test_dropbox_delete_commits_metadata_before_remote_cleanup(
    client, db_session, monkeypatch
):
    """A Dropbox outage must not leave a deleted row with missing source bytes."""
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    dropbox_path = f"/hydenlyne/{crew_id}/documents/cert/{document_id}_cert.pdf"
    db_session.add(
        CrewMember(
            id=crew_id,
            full_name="Dropbox Delete Contractor",
            publication_status="approved",
        )
    )
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew_id,
            file_name="cert.pdf",
            file_type="pdf",
            file_size=16,
            storage_type="dropbox",
            storage_path=dropbox_path,
            dropbox_path=dropbox_path,
        )
    )
    await db_session.commit()

    remote_delete = AsyncMock(return_value=False)
    queue_cleanup = MagicMock()
    monkeypatch.setattr(document_upload_service, "delete_from_dropbox", remote_delete)
    monkeypatch.setattr(document_upload_service, "delete_file", MagicMock())
    monkeypatch.setattr("app.tasks.document_tasks.queue_orphaned_upload_cleanup", queue_cleanup)
    monkeypatch.setattr(
        "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
        AsyncMock(return_value=True),
    )

    response = await client.delete(f"/api/documents/{document_id}")

    assert response.status_code == 204
    remote_delete.assert_awaited_once_with(dropbox_path)
    queue_cleanup.assert_called_once_with("dropbox", dropbox_path)
    async with get_session_factory()() as session:
        assert await session.get(Document, document_id) is None


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
async def test_staff_cannot_use_manual_document_upload(client, db_session, monkeypatch):
    staff = CrewMember(id=str(uuid.uuid4()), full_name="Manual Upload Staff", role="staff")
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Approved Upload Target",
        publication_status="approved",
    )
    db_session.add_all([staff, crew])
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )

    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": crew.id},
        files={"file": ("manual.pdf", io.BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_staff_can_upload_cv_to_own_draft(client, db_session, monkeypatch):
    staff = CrewMember(id=str(uuid.uuid4()), full_name="CV Staff", role="staff")
    draft = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Owned CV Draft",
        publication_status="draft",
        submitted_by=staff.id,
    )
    db_session.add_all([staff, draft])
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )
    monkeypatch.setattr("app.api.documents.process_document_extraction.delay", lambda _id: None)

    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": draft.id, "classification": "cv"},
        files={"file": ("owned-cv.pdf", io.BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_staff_cv_upload_rechecks_draft_after_file_storage(
    client, db_session, monkeypatch
):
    """A draft changed during slow storage must not accept the CV metadata."""
    from app.database import get_session_factory

    staff = CrewMember(id=str(uuid.uuid4()), full_name="Race Staff", role="staff")
    draft = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Race Draft",
        publication_status="draft",
        submitted_by=staff.id,
    )
    db_session.add_all([staff, draft])
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )

    async def save_file_and_reject(_file, crew_id, _classification):
        async with get_session_factory()() as session:
            current = await session.get(CrewMember, crew_id)
            assert current is not None
            current.publication_status = "rejected"
            await session.commit()
        return str(uuid.uuid4()), "/tmp/raced-cv.pdf", 10

    monkeypatch.setattr(document_upload_service, "save_file", save_file_and_reject)
    monkeypatch.setattr("app.api.documents.process_document_extraction.delay", lambda _id: None)

    response = await client.post(
        "/api/documents/upload",
        data={"crew_id": draft.id, "classification": "cv"},
        files={"file": ("raced-cv.pdf", io.BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")},
    )

    assert response.status_code == 403
    assert (
        await db_session.execute(select(Document).where(Document.crew_member_id == draft.id))
    ).scalars().all() == []


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


@pytest.mark.asyncio
async def test_staff_cannot_get_status_for_document_with_missing_crew(
    client, db_session, monkeypatch
):
    """An orphaned document must fail closed for non-admin metadata access."""
    from app.services.crew import auth_service

    staff = CrewMember(id=str(uuid.uuid4()), full_name="Status Staff", role="staff")
    document = Document(
        id=str(uuid.uuid4()),
        crew_member_id=str(uuid.uuid4()),
        file_name="orphan.pdf",
        file_type="pdf",
        file_size=10,
        storage_type="local",
        storage_path="/tmp/orphan.pdf",
    )
    db_session.add(document)
    await db_session.commit()
    monkeypatch.setattr(auth_service, "get_user_from_token", AsyncMock(return_value=staff))

    response = await client.get(f"/api/documents/{document.id}/status")

    assert response.status_code == 404


def test_dropbox_cache_uses_crew_id_not_classification():
    """A Dropbox path must map to the cache created during upload."""
    cache_path = document_upload_service._get_local_cache_path(
        "/hydenlyne/crew-123/documents/cv/document-123_candidate.pdf"
    )
    assert (
        cache_path == document_upload_service.cache_path / "crew-123" / "document-123_candidate.pdf"
    )


@pytest.mark.asyncio
async def test_resolve_incoming_document_review_approve(client, db_session):
    """Staff approving an incoming document sets review resolved and document approved."""
    from app.services.document_requests import document_request_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(id=crew_id, full_name="Approve Test Specialist", publication_status="approved")
    )
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/cert.pdf",
        uploaded_by="contractor-upload-link",
        extraction_status="needs_review",
    )
    db_session.add(doc)
    await db_session.commit()

    req = await document_request_service.create(
        crew_id=crew_id, actor_id=crew_id, actor_role="staff", expires_in_days=14
    )
    await document_request_service.create_review(request_id=req.request_id, document_id=doc_id)

    queue = await client.get("/api/documents/review-queue")
    assert queue.status_code == 200
    assert len(queue.json()) >= 1
    review_id = queue.json()[0]["id"]

    res = await client.post(
        f"/api/documents/review-queue/{review_id}/action",
        data={"action": "approve", "note": "Valid OPITO certificate"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "resolved"
    assert res.json()["document_id"] == doc_id

    # Verify document extraction_status is now approved
    await db_session.refresh(doc)
    assert doc.extraction_status == "approved"

    # Verify review queue is now empty of this resolved item
    queue_after = await client.get("/api/documents/review-queue")
    assert not any(item["id"] == review_id for item in queue_after.json())


@pytest.mark.asyncio
async def test_approving_reviewed_certificate_rebuilds_certification_projection(client, db_session):
    """Human approval must publish the extracted certificate projection."""
    from app.services.document_requests import document_request_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    crew = CrewMember(
        id=crew_id,
        full_name="Certificate Review Specialist",
        publication_status="approved",
    )
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="bosiet.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/bosiet.pdf",
        uploaded_by="contractor-upload-link",
        classification="certificate",
        extraction_status="needs_review",
        extracted_data={
            "certificate_type": "BOSIET",
            "certificate_number": "BOS-123",
            "issuing_body": "RelyOn Nutec",
        },
    )
    db_session.add_all([crew, doc])
    await db_session.commit()

    req = await document_request_service.create(
        crew_id=crew_id, actor_id=crew_id, actor_role="staff", expires_in_days=14
    )
    await document_request_service.create_review(request_id=req.request_id, document_id=doc_id)

    response = await client.post(
        f"/api/documents/{doc_id}/review",
        data={"action": "approve", "note": "Certificate checked"},
    )

    assert response.status_code == 200
    cert = (
        await db_session.execute(select(Certification).where(Certification.document_ref == doc_id))
    ).scalar_one()
    assert cert.crew_member_id == crew_id
    assert cert.cert_type == "BOSIET"
    assert cert.cert_number == "BOS-123"


@pytest.mark.asyncio
async def test_certificate_projection_failure_reopens_document_review(db_session):
    """A failed post-approval projection must leave the evidence retryable."""
    from app.services.document_requests import document_request_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    crew = CrewMember(
        id=crew_id, full_name="Projection Retry Specialist", publication_status="approved"
    )
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="retry-cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/retry-cert.pdf",
        uploaded_by="contractor-upload-link",
        classification="certificate",
        extraction_status="needs_review",
        extracted_data={"certificate_type": "BOSIET"},
    )
    db_session.add_all([crew, doc])
    await db_session.commit()

    request = await document_request_service.create(
        crew_id=crew_id, actor_id=crew_id, actor_role="staff", expires_in_days=14
    )
    await document_request_service.create_review(request_id=request.request_id, document_id=doc_id)
    review = (
        await db_session.execute(
            select(IncomingDocumentReview).where(IncomingDocumentReview.document_id == doc_id)
        )
    ).scalar_one()

    with (
        patch(
            "app.services.crew.certification_service.link_extracted_certificate",
            new=AsyncMock(side_effect=RuntimeError("projection unavailable")),
        ),
        patch(
            "app.services.document_requests.cache_service.delete", new=AsyncMock()
        ) as delete_cache,
        patch(
            "app.services.qdrant.qdrant_service.delete_document", new=AsyncMock()
        ) as delete_vector,
    ):
        settings = get_settings()
        previous_semantic_flag = settings.ENABLE_SEMANTIC_SEARCH
        settings.ENABLE_SEMANTIC_SEARCH = True
        with pytest.raises(RuntimeError, match="projection unavailable"):
            try:
                await document_request_service.resolve_review(
                    review_id=review.id,
                    actor_id=crew_id,
                    actor_role="staff",
                    action="approve",
                )
            finally:
                settings.ENABLE_SEMANTIC_SEARCH = previous_semantic_flag

    await db_session.refresh(doc)
    await db_session.refresh(review)
    assert doc.extraction_status == "needs_review"
    assert review.status == "unread"
    assert delete_cache.await_count == 2
    delete_vector.assert_awaited_once_with(doc_id)


@pytest.mark.asyncio
async def test_repeated_approval_queues_certificate_projection_repair(client, db_session):
    """A resolved approval remains an idempotent repair trigger."""
    from app.services.document_requests import document_request_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    crew = CrewMember(id=crew_id, full_name="Resolved Repair Specialist", publication_status="approved")
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="repair-cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/repair-cert.pdf",
        uploaded_by="contractor-upload-link",
        classification="certificate",
        extraction_status="approved",
        extracted_data={"certificate_type": "BOSIET"},
    )
    db_session.add_all([crew, doc])
    await db_session.commit()
    request = await document_request_service.create(
        crew_id=crew_id, actor_id=crew_id, actor_role="staff", expires_in_days=14
    )
    await document_request_service.create_review(request_id=request.request_id, document_id=doc_id)
    review = (
        await db_session.execute(
            select(IncomingDocumentReview).where(IncomingDocumentReview.document_id == doc_id)
        )
    ).scalar_one()
    review.status = "resolved"
    await db_session.commit()

    with (
        patch(
            "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
            new=AsyncMock(return_value=True),
        ),
        patch("app.tasks.document_tasks.queue_certificate_projection_reconcile") as queue_repair,
        patch("app.services.document_requests.cache_service.delete", new=AsyncMock()) as delete_cache,
    ):
        await document_request_service.resolve_review(
            review_id=review.id,
            actor_id=crew_id,
            actor_role="staff",
            action="approve",
        )

    queue_repair.assert_called_once_with(doc_id)
    assert delete_cache.await_count == 2


@pytest.mark.asyncio
async def test_resolve_incoming_document_review_reject(client, db_session):
    """Staff rejecting an incoming document sets review rejected and document rejected."""
    from app.services.document_requests import document_request_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    crew = CrewMember(
        id=crew_id,
        full_name="Reject Test Specialist",
        publication_status="approved",
        medical_expiry=date(2028, 1, 1),
        medical_status="fit",
    )
    db_session.add(crew)
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="expired_cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/expired_cert.pdf",
        uploaded_by="contractor-upload-link",
        extraction_status="pending",
    )
    db_session.add(doc)
    certification = Certification(
        id=str(uuid.uuid4()),
        crew_member_id=crew_id,
        cert_type="OGUK Medical",
        expiry_date=date(2028, 1, 1),
        document_ref=doc_id,
        status="valid",
        verification_status="verified",
    )
    db_session.add(certification)
    await db_session.commit()

    req = await document_request_service.create(
        crew_id=crew_id, actor_id=crew_id, actor_role="staff", expires_in_days=14
    )
    await document_request_service.create_review(request_id=req.request_id, document_id=doc_id)

    queue = await client.get("/api/documents/review-queue")
    review_id = queue.json()[0]["id"]

    settings = get_settings()
    previous_semantic_flag = settings.ENABLE_SEMANTIC_SEARCH
    settings.ENABLE_SEMANTIC_SEARCH = True
    try:
        with patch(
            "app.services.qdrant.qdrant_service.delete_document",
            new=AsyncMock(),
        ) as delete_document:
            res = await client.post(
                f"/api/documents/review-queue/{review_id}/action",
                data={"action": "reject", "note": "Expired document"},
            )
            delete_document.assert_awaited_once_with(doc_id)
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = previous_semantic_flag
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    await db_session.refresh(doc)
    await db_session.refresh(crew)
    await db_session.refresh(certification)
    assert doc.extraction_status == "rejected"
    assert certification.document_ref is None
    assert certification.verification_status == "unverified"
    assert certification.status == "pending_verification"
    assert crew.medical_expiry is None
    assert crew.medical_status is None


@pytest.mark.asyncio
async def test_approved_review_can_retry_projection_after_commit(client, db_session):
    """A committed approval remains repairable when Meilisearch is unavailable."""
    from app.services.document_requests import document_request_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(id=crew_id, full_name="Projection Retry Approval", publication_status="approved")
    )
    db_session.add(
        Document(
            id=doc_id,
            crew_member_id=crew_id,
            file_name="certificate.pdf",
            file_type="pdf",
            file_size=123,
            storage_type="local",
            storage_path="/tmp/certificate.pdf",
            uploaded_by="contractor-upload-link",
            classification="certificate",
            extraction_status="needs_review",
            extracted_data={"certificate_type": "STCW"},
        )
    )
    await db_session.commit()
    request = await document_request_service.create(
        crew_id=crew_id, actor_id=crew_id, actor_role="staff", expires_in_days=14
    )
    await document_request_service.create_review(request_id=request.request_id, document_id=doc_id)
    review = (
        await db_session.execute(
            select(IncomingDocumentReview).where(IncomingDocumentReview.document_id == doc_id)
        )
    ).scalar_one()

    with patch(
        "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
        new=AsyncMock(side_effect=RuntimeError("meilisearch unavailable")),
    ):
        first = await client.post(
            f"/api/documents/review-queue/{review.id}/action",
            data={"action": "approve"},
        )
    assert first.status_code == 200, first.text
    assert first.json()["extraction_status"] == "approved"

    with patch(
        "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
        new=AsyncMock(return_value=True),
    ) as reconcile:
        second = await client.post(
            f"/api/documents/review-queue/{review.id}/action",
            data={"action": "approve"},
        )
    assert second.status_code == 200, second.text
    reconcile.assert_awaited_once_with(doc_id)


@pytest.mark.asyncio
async def test_cannot_approve_incoming_document_before_extraction(client, db_session):
    """Approval must not make a pending document bypass extraction review."""
    from app.services.document_requests import document_request_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id, full_name="Pending Approval Specialist", publication_status="approved"
        )
    )
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="pending.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/pending.pdf",
        extraction_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()

    req = await document_request_service.create(
        crew_id=crew_id, actor_id=crew_id, actor_role="staff", expires_in_days=14
    )
    await document_request_service.create_review(request_id=req.request_id, document_id=doc_id)

    response = await client.post(
        f"/api/documents/{doc_id}/review",
        data={"action": "approve", "note": "Premature approval should be rejected"},
    )

    assert response.status_code == 400
    assert "not ready for approval" in response.json()["detail"]
    await db_session.refresh(doc)
    assert doc.extraction_status == "pending"


@pytest.mark.asyncio
async def test_staff_cannot_resolve_other_staff_draft_reviews(client, db_session, monkeypatch):
    """Staff cannot approve/reject reviews belonging to another staff member's draft."""
    from app.services.crew import auth_service
    from app.services.document_requests import document_request_service

    owner_id = str(uuid.uuid4())
    other_staff_id = str(uuid.uuid4())
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    db_session.add(
        CrewMember(
            id=crew_id,
            full_name="Private Draft Specialist",
            publication_status="draft",
            submitted_by=owner_id,
        )
    )
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="draft_doc.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/draft_doc.pdf",
    )
    db_session.add(doc)
    await db_session.commit()

    req = await document_request_service.create(
        crew_id=crew_id, actor_id=owner_id, actor_role="staff", expires_in_days=14
    )
    await document_request_service.create_review(request_id=req.request_id, document_id=doc_id)

    review = (
        await db_session.execute(
            select(IncomingDocumentReview).where(IncomingDocumentReview.document_id == doc_id)
        )
    ).scalar_one()

    # Log in as other staff
    acting_staff = CrewMember(id=other_staff_id, full_name="Snooping Staff", role="staff")
    monkeypatch.setattr(auth_service, "get_user_from_token", AsyncMock(return_value=acting_staff))

    res = await client.post(
        f"/api/documents/review-queue/{review.id}/action",
        data={"action": "approve"},
    )
    assert res.status_code == 403
    assert "belongs to another user" in res.json()["detail"]


@pytest.mark.asyncio
async def test_resolve_document_review_by_document_id(client, db_session):
    """Reviewing directly by document ID approves document and marks any active review queue item resolved."""
    from app.services.document_requests import document_request_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id, full_name="Direct Doc Review Specialist", publication_status="approved"
        )
    )
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="direct_cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/direct_cert.pdf",
        uploaded_by="contractor-upload-link",
        extraction_status="needs_review",
    )
    db_session.add(doc)
    await db_session.commit()

    req = await document_request_service.create(
        crew_id=crew_id, actor_id=crew_id, actor_role="staff", expires_in_days=14
    )
    await document_request_service.create_review(request_id=req.request_id, document_id=doc_id)

    res = await client.post(
        f"/api/documents/{doc_id}/review",
        data={"action": "approve", "note": "Verified by operations lead"},
    )
    assert res.status_code == 200
    assert res.json()["document_id"] == doc_id
    assert res.json()["extraction_status"] == "approved"

    await db_session.refresh(doc)
    assert doc.extraction_status == "approved"

    # Verify review queue item is resolved
    queue = await client.get("/api/documents/review-queue")
    assert not any(item["document_id"] == doc_id for item in queue.json())


@pytest.mark.asyncio
async def test_staff_cannot_review_an_admin_uploaded_document_by_id(
    client, db_session, monkeypatch
):
    from app.services.crew import auth_service

    acting_staff = CrewMember(id="staff-1", full_name="Reviewing Staff", role="staff")
    monkeypatch.setattr(auth_service, "get_user_from_token", AsyncMock(return_value=acting_staff))

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id,
            full_name="Admin Upload Boundary Specialist",
            publication_status="approved",
        )
    )
    db_session.add(
        Document(
            id=doc_id,
            crew_member_id=crew_id,
            file_name="admin-uploaded.pdf",
            file_type="pdf",
            file_size=123,
            storage_type="local",
            storage_path="/tmp/admin-uploaded.pdf",
            uploaded_by="admin-1",
            classification="certificate",
            extraction_status="needs_review",
            extracted_data={"certificate_type": "BOSIET"},
        )
    )
    await db_session.commit()

    response = await client.post(
        f"/api/documents/{doc_id}/review",
        data={"action": "approve"},
    )

    assert response.status_code == 403
    doc = (await db_session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.extraction_status == "needs_review"


@pytest.mark.asyncio
async def test_direct_document_review_cannot_bypass_cv_review_workflow(client, db_session):
    """CV decisions must use the administrator-only structured review flow."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id,
            full_name="CV Workflow Boundary Specialist",
            publication_status="approved",
        )
    )
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="cv.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/cv.pdf",
        classification="cv",
        extraction_status="awaiting_review",
    )
    db_session.add(doc)
    await db_session.commit()

    res = await client.post(
        f"/api/documents/{doc_id}/review",
        data={"action": "approve"},
    )

    assert res.status_code == 400
    assert "administrator CV review workflow" in res.json()["detail"]
    await db_session.refresh(doc)
    assert doc.extraction_status == "awaiting_review"


@pytest.mark.asyncio
async def test_direct_document_review_cannot_overwrite_terminal_decision(client, db_session):
    """A known document ID must not reopen an approved document for staff review."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id,
            full_name="Terminal Review Boundary Specialist",
            publication_status="approved",
        )
    )
    doc = Document(
        id=doc_id,
        crew_member_id=crew_id,
        file_name="approved_cert.pdf",
        file_type="pdf",
        file_size=123,
        storage_type="local",
        storage_path="/tmp/approved_cert.pdf",
        classification="certificate",
        extraction_status="approved",
    )
    db_session.add(doc)
    await db_session.commit()

    response = await client.post(
        f"/api/documents/{doc_id}/review",
        data={"action": "reject"},
    )

    assert response.status_code == 400
    assert "already been resolved" in response.json()["detail"]
    await db_session.refresh(doc)
    assert doc.extraction_status == "approved"


@pytest.mark.asyncio
async def test_rejected_document_review_retry_repeats_vector_cleanup(db_session):
    from app.services.document_requests import document_request_service

    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id, full_name="Rejected Upload Specialist", publication_status="approved"
        )
    )
    db_session.add(
        Document(
            id=doc_id,
            crew_member_id=crew_id,
            file_name="rejected-certificate.pdf",
            file_type="pdf",
            file_size=123,
            storage_type="local",
            storage_path=f"/tmp/{doc_id}.pdf",
            classification="certificate",
            extraction_status="rejected",
        )
    )
    await db_session.commit()
    request = await document_request_service.create(
        crew_id=crew_id, actor_id="staff-1", actor_role="staff", expires_in_days=14
    )
    db_session.add(
        IncomingDocumentReview(
            id=review_id,
            request_id=request.request_id,
            document_id=doc_id,
            status="rejected",
        )
    )
    await db_session.commit()

    settings = get_settings()
    previous_semantic_flag = settings.ENABLE_SEMANTIC_SEARCH
    settings.ENABLE_SEMANTIC_SEARCH = True
    try:
        with patch(
            "app.services.qdrant.qdrant_service.delete_document", new=AsyncMock()
        ) as delete_vector:
            with pytest.raises(ValueError, match="already been resolved"):
                await document_request_service.resolve_review(
                    review_id=review_id,
                    actor_id="staff-1",
                    actor_role="staff",
                    action="reject",
                )
            delete_vector.assert_awaited_once_with(doc_id)
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = previous_semantic_flag


@pytest.mark.asyncio
async def test_agent_upload_marks_document_failed_when_task_queue_is_unavailable(
    client, db_session, monkeypatch
):
    """A broker outage must be visible instead of leaving permanent pending state."""
    settings = get_settings()
    monkeypatch.setattr(settings, "API_KEY", "test-agent-key")
    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Agent Queue Failure"))
    await db_session.commit()

    monkeypatch.setattr(
        "app.api.documents.process_document_extraction.delay",
        MagicMock(side_effect=RuntimeError("broker unavailable")),
    )
    response = await client.post(
        "/api/documents/agent/upload",
        data={"crew_id": crew_id, "classification": "certificate"},
        files={
            "file": ("queue-failure.pdf", io.BytesIO(b"%PDF-1.4\nagent\n%%EOF"), "application/pdf")
        },
        headers={"X-API-Key": "test-agent-key"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    document = (
        await db_session.execute(select(Document).where(Document.id == response.json()["id"]))
    ).scalar_one()
    assert document.extraction_status == "failed"


def test_vision_extraction_rejects_oversize_image(tmp_path):
    """Oversize images must fail fast, not become OOM-sized LLM payloads."""
    from app.services.extraction import MAX_IMAGE_BYTES, extraction_service

    big = tmp_path / "big.png"
    big.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_IMAGE_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        extraction_service.extract_from_image_sync(str(big), "certificate")


@pytest.mark.asyncio
async def test_agent_upload_rejects_unknown_crew_and_dedupes_retries(
    client, db_session, monkeypatch
):
    """Agent path: 404 on unknown crew; same idempotency key returns one row."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "API_KEY", "test-agent-key")
    headers = {"X-API-Key": "test-agent-key"}

    missing = await client.post(
        "/api/documents/agent/upload",
        data={"crew_id": str(uuid.uuid4()), "classification": "certificate"},
        files={"file": ("ghost.pdf", io.BytesIO(b"%PDF-1.4\nghost\n%%EOF"), "application/pdf")},
        headers=headers,
    )
    assert missing.status_code == 404

    crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=crew_id, full_name="Agent Retry Contractor"))
    await db_session.commit()

    collision_crew_id = str(uuid.uuid4())
    db_session.add(CrewMember(id=collision_crew_id, full_name="Agent Collision Contractor"))
    db_session.add(
        Document(
            id=str(uuid.uuid4()),
            crew_member_id=collision_crew_id,
            file_name="staff.pdf",
            file_type="pdf",
            file_size=10,
            storage_type="local",
            storage_path="/tmp/staff.pdf",
            upload_key="shared-channel-key",
            uploaded_by="admin-1",
        )
    )
    await db_session.commit()
    collision = await client.post(
        "/api/documents/agent/upload",
        data={
            "crew_id": collision_crew_id,
            "classification": "certificate",
            "idempotency_key": "shared-channel-key",
        },
        files={"file": ("agent.pdf", io.BytesIO(b"%PDF-1.4\nagent\n%%EOF"), "application/pdf")},
        headers=headers,
    )
    assert collision.status_code == 409

    db_session.add(
        Document(
            id=str(uuid.uuid4()),
            crew_member_id=crew_id,
            file_name="agent-owned.pdf",
            file_type="pdf",
            file_size=10,
            storage_type="local",
            storage_path="/tmp/agent-owned.pdf",
            upload_key="agent-owned-key",
            uploaded_by="agent",
        )
    )
    await db_session.commit()
    reverse_collision = await client.post(
        "/api/documents/upload",
        data={
            "crew_id": crew_id,
            "classification": "certificate",
            "idempotency_key": "agent-owned-key",
        },
        files={"file": ("staff.pdf", io.BytesIO(b"%PDF-1.4\nstaff\n%%EOF"), "application/pdf")},
    )
    assert reverse_collision.status_code == 409

    form = {"crew_id": crew_id, "classification": "cert", "idempotency_key": "agent-retry-1"}
    payload = {"file": ("a.pdf", io.BytesIO(b"%PDF-1.4\nagent\n%%EOF"), "application/pdf")}
    first = await client.post(
        "/api/documents/agent/upload", data=form, files=payload, headers=headers
    )
    second = await client.post(
        "/api/documents/agent/upload",
        data=form,
        files={"file": ("a.pdf", io.BytesIO(b"%PDF-1.4\nagent\n%%EOF"), "application/pdf")},
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    # Stored classification is the normalized canonical value, not "cert".
    docs = (
        (
            await db_session.execute(
                select(Document).where(
                    Document.crew_member_id == crew_id,
                    Document.upload_key == "agent-retry-1",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(docs) == 1
    assert docs[0].classification == "certificate"
    assert docs[0].upload_key == "agent-retry-1"
    assert (await client.delete(f"/api/documents/{first.json()['id']}")).status_code == 204


@pytest.mark.asyncio
async def test_agent_upload_rejects_rejected_crew(client, db_session, monkeypatch):
    """Machine uploads must not add evidence to a rejected profile."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "API_KEY", "test-agent-key")
    crew_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id,
            full_name="Rejected Agent Contractor",
            publication_status="rejected",
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/documents/agent/upload",
        data={"crew_id": crew_id, "classification": "certificate"},
        files={
            "file": (
                "rejected.pdf",
                io.BytesIO(b"%PDF-1.4\nrejected\n%%EOF"),
                "application/pdf",
            )
        },
        headers={"X-API-Key": "test-agent-key"},
    )

    assert response.status_code == 404
    assert not (
        await db_session.execute(select(Document).where(Document.crew_member_id == crew_id))
    ).scalars().all()
