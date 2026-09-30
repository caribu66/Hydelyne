from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from celery.exceptions import Retry

from app.tasks.document_tasks import (
    _reconcile_document_search,
    check_expiring_certifications,
    cleanup_deleted_crew_projections,
    cleanup_document_projections,
    cleanup_local_document_cache,
    cleanup_orphaned_upload,
    index_document_embeddings,
    reconcile_certificate_projection,
    reconcile_crew_projection,
    reconcile_document_search_projection,
)


class _AsyncSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


class _AsyncSessionResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def test_document_processing_preserves_review_terminal_status(monkeypatch):
    """A review racing extraction must not turn the committed decision into failure."""
    from app.services import document_service

    original_doc = SimpleNamespace(
        id="document-1",
        extraction_status="pending",
        extracted_data=None,
        dropbox_revision=None,
        classification="certificate",
        file_type="pdf",
        file_name="certificate.pdf",
        storage_path="/tmp/certificate.pdf",
        storage_type="local",
        dropbox_path=None,
        crew_member_id="crew-1",
        uploaded_by="staff-1",
    )
    reviewed_doc = SimpleNamespace(**{**original_doc.__dict__, "extraction_status": "rejected"})
    first_session = MagicMock()
    first_session.execute = AsyncMock(return_value=_AsyncSessionResult(original_doc))
    first_session.commit = AsyncMock()
    second_session = MagicMock()
    second_session.execute = AsyncMock(return_value=_AsyncSessionResult(reviewed_doc))
    second_session.commit = AsyncMock()

    sessions = iter([first_session, second_session])
    monkeypatch.setattr(
        document_service,
        "get_session_factory",
        lambda: lambda: _AsyncSessionContext(next(sessions)),
    )
    monkeypatch.setattr(
        document_service.text_extraction_service,
        "is_image",
        lambda _file_type: False,
    )
    monkeypatch.setattr(
        document_service.document_upload_service,
        "get_file_async",
        AsyncMock(return_value=b"pdf bytes"),
    )
    monkeypatch.setattr(
        document_service.document_upload_service,
        "validate_file_content",
        lambda *_args: (True, ""),
    )
    monkeypatch.setattr(
        document_service.text_extraction_service,
        "extract_text",
        AsyncMock(return_value="certificate text"),
    )
    monkeypatch.setattr(
        document_service.extraction_service,
        "extract_document",
        AsyncMock(return_value={"document_type": "certificate"}),
    )
    monkeypatch.setattr(
        document_service.extraction_service,
        "determine_review_status",
        lambda _result: ("extracted", False),
    )
    monkeypatch.setattr(
        document_service.extraction_service,
        "confidence_from_result",
        lambda _result: {},
    )
    monkeypatch.setattr(document_service, "_log_extraction_best_effort", AsyncMock())
    knowledge = MagicMock()
    knowledge.reconcile_document_index = AsyncMock(return_value=True)
    monkeypatch.setattr(document_service, "consultant_knowledge_service", knowledge, raising=False)

    result = __import__("asyncio").run(
        document_service.document_service.process_document("document-1")
    )

    assert result["status"] == "rejected"


def test_expiring_certification_task_retries_failures():
    """A transient compliance failure must not be acknowledged as success."""
    session = MagicMock()
    with (
        patch("app.services.sync_processor.get_sync_session", return_value=session),
        patch(
            "app.services.compliance.compliance_service.evaluate_and_update_compliance_sync",
            side_effect=RuntimeError("database unavailable"),
        ),
        patch.object(check_expiring_certifications, "retry", side_effect=Retry()),
    ):
        with pytest.raises(Retry):
            check_expiring_certifications.run()

    session.close.assert_called_once_with()


class _Result:
    def __init__(self, document):
        self.document = document

    def scalar_one_or_none(self):
        return self.document


class _Session:
    def __init__(self, documents):
        self.documents = iter(documents)

    def expire_all(self):
        pass

    def execute(self, _statement):
        return _Result(next(self.documents))

    def get(self, _model, _crew_id):
        return SimpleNamespace(publication_status="approved")

    def rollback(self):
        pass

    def close(self):
        pass


def test_embedding_task_excludes_login_account_documents():
    account_document = SimpleNamespace(
        id="document-1",
        file_name="staff-certificate.pdf",
        classification="certificate",
        crew_member_id="staff-1",
        extraction_status="approved",
        uploaded_by="admin-1",
        dropbox_revision="rev-1",
    )

    class _AccountSession(_Session):
        def get(self, _model, _crew_id):
            return SimpleNamespace(
                publication_status="approved",
                password_hash="stored-password-hash",
                role="staff",
            )

    session = _AccountSession([account_document])
    qdrant = MagicMock()

    with (
        patch("app.services.sync_processor.get_sync_session", return_value=session),
        patch("app.services.qdrant.qdrant_service", qdrant),
    ):
        result = index_document_embeddings.run("document-1")

    assert result == {
        "document_id": "document-1",
        "status": "skipped",
        "reason": "contractor is not published",
    }
    qdrant.index_document_sync.assert_not_called()
    qdrant.delete_document_sync.assert_called_once_with("document-1")


def test_embedding_task_removes_vector_when_revision_changes_during_upsert():
    old_doc = SimpleNamespace(
        id="document-1",
        file_name="certificate.pdf",
        classification="certificate",
        crew_member_id="crew-1",
        extraction_status="approved",
        uploaded_by="admin-1",
        dropbox_revision="rev-old",
    )
    new_doc = SimpleNamespace(**{**old_doc.__dict__, "dropbox_revision": "rev-new"})
    session = _Session([old_doc, new_doc])
    qdrant = MagicMock()
    qdrant.index_document_sync.return_value = True

    with (
        patch("app.services.sync_processor.get_sync_session", return_value=session),
        patch("app.services.qdrant.qdrant_service", qdrant),
        patch("app.tasks.document_tasks.index_document_embeddings.delay") as requeue,
    ):
        result = index_document_embeddings.run("document-1")

    assert result == {
        "document_id": "document-1",
        "status": "skipped",
        "reason": "document changed during indexing",
    }
    qdrant.index_document_sync.assert_called_once()
    qdrant.delete_document_sync.assert_called_once_with("document-1")
    requeue.assert_called_once_with("document-1")


def test_embedding_task_retries_when_changed_revision_cannot_be_requeued():
    old_doc = SimpleNamespace(
        id="document-1",
        file_name="certificate.pdf",
        classification="certificate",
        crew_member_id="crew-1",
        extraction_status="approved",
        uploaded_by="admin-1",
        dropbox_revision="rev-old",
    )
    new_doc = SimpleNamespace(**{**old_doc.__dict__, "dropbox_revision": "rev-new"})
    session = _Session([old_doc, new_doc])
    qdrant = MagicMock()
    qdrant.index_document_sync.return_value = True

    with (
        patch("app.services.sync_processor.get_sync_session", return_value=session),
        patch("app.services.qdrant.qdrant_service", qdrant),
        patch(
            "app.tasks.document_tasks.index_document_embeddings.delay",
            side_effect=RuntimeError("broker unavailable"),
        ),
        patch.object(index_document_embeddings, "retry", side_effect=Retry()),
    ):
        with pytest.raises(Retry):
            index_document_embeddings.run("document-1")

    qdrant.delete_document_sync.assert_called_once_with("document-1")


def test_embedding_task_removes_orphaned_vector_when_document_is_no_longer_searchable():
    rejected_doc = SimpleNamespace(
        id="document-1",
        file_name="certificate.pdf",
        classification="certificate",
        crew_member_id="crew-1",
        extraction_status="rejected",
        uploaded_by="admin-1",
        dropbox_revision="rev-old",
    )
    session = _Session([rejected_doc])
    qdrant = MagicMock()

    with (
        patch("app.services.sync_processor.get_sync_session", return_value=session),
        patch("app.services.qdrant.qdrant_service", qdrant),
    ):
        result = index_document_embeddings.run("document-1")

    assert result == {
        "document_id": "document-1",
        "status": "skipped",
        "reason": "document is not searchable",
    }
    qdrant.index_document_sync.assert_not_called()
    qdrant.delete_document_sync.assert_called_once_with("document-1")


def test_embedding_task_queues_cleanup_when_orphan_vector_delete_is_unconfirmed():
    session = _Session([None])
    qdrant = MagicMock()
    qdrant.delete_document_sync.return_value = False

    with (
        patch("app.services.sync_processor.get_sync_session", return_value=session),
        patch("app.services.qdrant.qdrant_service", qdrant),
        patch("app.tasks.document_tasks.queue_document_projection_cleanup") as queue_cleanup,
    ):
        result = index_document_embeddings.run("document-1")

    assert result == {
        "document_id": "document-1",
        "status": "failed",
        "error": "not found",
    }
    queue_cleanup.assert_called_once_with("document-1")


def test_embedding_task_removes_previous_vector_when_replacement_fails():
    document = SimpleNamespace(
        id="document-1",
        file_name="certificate.pdf",
        classification="certificate",
        crew_member_id="crew-1",
        extraction_status="approved",
        uploaded_by="admin-1",
        dropbox_revision="rev-old",
    )
    session = _Session([document])
    qdrant = MagicMock()
    qdrant.index_document_sync.return_value = False

    with (
        patch("app.services.sync_processor.get_sync_session", return_value=session),
        patch("app.services.qdrant.qdrant_service", qdrant),
        patch.object(index_document_embeddings, "retry", side_effect=Retry()),
    ):
        with pytest.raises(Retry):
            index_document_embeddings.run("document-1")

    qdrant.delete_document_sync.assert_called_once_with("document-1")


def test_deleted_crew_cleanup_removes_all_derived_projections():
    cache = MagicMock()
    cache.delete = AsyncMock()
    knowledge = MagicMock()
    knowledge.remove_from_index = AsyncMock()
    qdrant = MagicMock()
    qdrant.delete_document = AsyncMock()

    with (
        patch("app.services.cache.cache_service", cache),
        patch("app.services.consultant_knowledge.consultant_knowledge_service", knowledge),
        patch("app.services.qdrant.qdrant_service", qdrant),
        patch(
            "app.tasks.document_tasks.get_settings",
            return_value=SimpleNamespace(ENABLE_SEMANTIC_SEARCH=True),
        ),
        patch("app.database.dispose_engine", new=AsyncMock()),
    ):
        result = cleanup_deleted_crew_projections.run("crew-1", ["document-1", "document-2"])

    assert result == {"crew_id": "crew-1", "status": "cleaned"}
    knowledge.remove_from_index.assert_awaited_once_with("crew-1")
    assert qdrant.delete_document.await_args_list == [
        (("document-1",), {}),
        (("document-2",), {}),
    ]
    assert cache.delete.await_count == 3


def test_document_projection_cleanup_requeues_current_searchable_document():
    knowledge = MagicMock()
    knowledge.reconcile_document_index = AsyncMock(return_value=True)
    qdrant = MagicMock()
    qdrant.delete_document = AsyncMock(return_value=True)

    with (
        patch("app.services.consultant_knowledge.consultant_knowledge_service", knowledge),
        patch("app.services.qdrant.qdrant_service", qdrant),
        patch(
            "app.tasks.document_tasks.get_settings",
            return_value=SimpleNamespace(ENABLE_SEMANTIC_SEARCH=True),
        ),
        patch("app.tasks.document_tasks._is_searchable_document", new=AsyncMock(return_value=True)),
        patch("app.tasks.document_tasks.index_document_embeddings.delay") as requeue,
        patch("app.database.dispose_engine", new=AsyncMock()),
    ):
        result = cleanup_document_projections.run("document-1")

    assert result == {"document_id": "document-1", "status": "cleaned"}
    qdrant.delete_document.assert_awaited_once_with("document-1")
    requeue.assert_called_once_with("document-1")


def test_crew_projection_reconcile_reads_current_publication_state():
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _model, _crew_id):
            return SimpleNamespace(id="crew-1", publication_status="approved")

    factory = MagicMock(return_value=_Session())
    knowledge = MagicMock()
    knowledge.index_crew_member = AsyncMock()

    with (
        patch("app.database.get_session_factory", return_value=factory),
        patch("app.services.consultant_knowledge.consultant_knowledge_service", knowledge),
        patch("app.database.dispose_engine", new=AsyncMock()),
    ):
        result = reconcile_crew_projection.run("crew-1")

    assert result == {"crew_id": "crew-1", "status": "reconciled"}
    knowledge.index_crew_member.assert_awaited_once()


def test_orphaned_upload_cleanup_retries_dropbox_object_then_local_cache():
    upload = MagicMock()
    upload.delete_from_dropbox = AsyncMock(return_value=True)
    upload.delete_file.return_value = True

    with patch("app.services.upload.document_upload_service", upload):
        result = cleanup_orphaned_upload.run("dropbox", "/hydenlyne/crew/orphan.pdf")

    assert result == {"storage_path": "/hydenlyne/crew/orphan.pdf", "status": "cleaned"}
    upload.delete_from_dropbox.assert_awaited_once_with("/hydenlyne/crew/orphan.pdf")
    upload.delete_file.assert_called_once_with("/hydenlyne/crew/orphan.pdf")


def test_orphaned_upload_cleanup_still_removes_local_cache_when_remote_is_unconfirmed():
    upload = MagicMock()
    upload.delete_from_dropbox = AsyncMock(return_value=False)
    upload.delete_file.return_value = True

    with (
        patch("app.services.upload.document_upload_service", upload),
        patch.object(cleanup_orphaned_upload, "retry", side_effect=RuntimeError) as retry,
    ):
        with pytest.raises(RuntimeError):
            cleanup_orphaned_upload.run("dropbox", "/hydenlyne/crew/orphan.pdf")

    upload.delete_file.assert_called_once_with("/hydenlyne/crew/orphan.pdf")
    retry.assert_called_once()


def test_sync_semantic_cleanup_queues_retry_when_provider_raises(monkeypatch):
    from app.services import sync_processor

    monkeypatch.setattr(sync_processor.settings, "ENABLE_SEMANTIC_SEARCH", True)
    with (
        patch(
            "app.services.qdrant.qdrant_service.delete_document_sync",
            side_effect=RuntimeError("qdrant unavailable"),
        ),
        patch("app.tasks.document_tasks.queue_document_projection_cleanup") as queue_cleanup,
    ):
        sync_processor._delete_semantic_projection("document-1")

    queue_cleanup.assert_called_once_with("document-1")


def test_sync_extraction_rolls_back_before_marking_failure(monkeypatch):
    from app.services import sync_processor

    monkeypatch.setattr(sync_processor.settings, "ENABLE_SEMANTIC_SEARCH", False)

    document = SimpleNamespace(
        id="document-1",
        extraction_status="pending",
        extracted_data=None,
        dropbox_revision=None,
        classification="other",
        file_type="pdf",
    )
    session = MagicMock()
    session.execute.side_effect = [_Result(document), _Result(document)]
    session.commit.side_effect = [None, None]

    with (
        patch("app.services.sync_processor.get_sync_session", return_value=session),
        patch(
            "app.services.upload.document_upload_service.get_file",
            side_effect=FileNotFoundError("missing cache"),
        ),
        patch("app.services.sync_processor._log_extraction_sync"),
    ):
        result = sync_processor.sync_processor.process("document-1")

    assert result == {"error": "Document extraction failed", "status": "failed"}
    session.rollback.assert_called_once_with()
    assert document.extraction_status == "failed"


def test_sync_extraction_rejects_documents_linked_to_login_accounts(monkeypatch):
    from app.services import sync_processor

    monkeypatch.setattr(sync_processor.settings, "ENABLE_SEMANTIC_SEARCH", False)

    document = SimpleNamespace(
        id="document-1",
        crew_member_id="staff-1",
        extraction_status="pending",
        extracted_data=None,
        dropbox_revision=None,
        classification="certificate",
    )
    session = MagicMock()
    session.execute.side_effect = [
        _Result(document),
        _Result(
            SimpleNamespace(
                password_hash="stored-password-hash",
                role="staff",
            )
        ),
    ]

    with patch("app.services.sync_processor.get_sync_session", return_value=session):
        result = sync_processor.sync_processor.process("document-1")

    assert result == {
        "document_id": "document-1",
        "status": "rejected",
        "classification": "certificate",
    }
    assert document.extraction_status == "rejected"
    session.commit.assert_called_once_with()
    assert "FOR UPDATE" in str(session.execute.call_args_list[1].args[0])


def test_local_document_cache_cleanup_retries_filesystem_failures():
    upload = MagicMock()
    upload.delete_file.side_effect = OSError("temporary filesystem failure")

    with patch("app.services.upload.document_upload_service", upload):
        with patch.object(cleanup_local_document_cache, "retry", side_effect=RuntimeError) as retry:
            with pytest.raises(RuntimeError):
                cleanup_local_document_cache.run("/tmp/cache/document.pdf")

    upload.delete_file.assert_called_once_with("/tmp/cache/document.pdf")
    retry.assert_called_once()


def test_local_cache_cleanup_resumes_dropbox_extraction_after_delete():
    upload = MagicMock()

    with (
        patch("app.services.upload.document_upload_service", upload),
        patch("app.tasks.document_tasks.process_dropbox_document.delay") as resume,
    ):
        result = cleanup_local_document_cache.run("/tmp/cache/document.pdf", "document-1")

    assert result == {"storage_path": "/tmp/cache/document.pdf", "status": "cleaned"}
    upload.delete_file.assert_called_once_with("/tmp/cache/document.pdf")
    resume.assert_called_once_with("document-1")


def test_deleted_crew_cleanup_retries_when_cache_deletion_is_unconfirmed():
    cache = MagicMock()
    cache.delete = AsyncMock(return_value=False)
    knowledge = MagicMock()
    knowledge.remove_from_index = AsyncMock()

    with (
        patch("app.services.cache.cache_service", cache),
        patch("app.services.consultant_knowledge.consultant_knowledge_service", knowledge),
        patch("app.database.dispose_engine", new=AsyncMock()),
    ):
        with patch.object(
            cleanup_deleted_crew_projections, "retry", side_effect=RuntimeError
        ) as retry:
            with pytest.raises(RuntimeError):
                cleanup_deleted_crew_projections.run("crew-1", [])

    knowledge.remove_from_index.assert_awaited_once_with("crew-1")
    retry.assert_called_once()


def test_document_search_reconcile_retries_when_provider_returns_false():
    knowledge = MagicMock()
    knowledge.reconcile_document_index = AsyncMock(return_value=False)

    with (
        patch("app.services.consultant_knowledge.consultant_knowledge_service", knowledge),
        patch("app.database.dispose_engine", new=AsyncMock()),
    ):
        with patch.object(
            reconcile_document_search_projection, "retry", side_effect=RuntimeError
        ) as retry:
            with pytest.raises(RuntimeError):
                reconcile_document_search_projection.run("document-1")

    knowledge.reconcile_document_index.assert_awaited_once_with("document-1")
    retry.assert_called_once()


def test_extraction_search_reconcile_queues_retry_when_provider_raises():
    knowledge = MagicMock()
    knowledge.reconcile_document_index = AsyncMock(side_effect=RuntimeError("search unavailable"))

    with (
        patch("app.services.consultant_knowledge.consultant_knowledge_service", knowledge),
        patch("app.database.dispose_engine", new=AsyncMock()),
        patch("app.tasks.document_tasks.queue_document_search_reconcile") as queue_search,
    ):
        _reconcile_document_search("document-1")

    knowledge.reconcile_document_index.assert_awaited_once_with("document-1")
    queue_search.assert_called_once_with("document-1")


def test_certificate_projection_reconcile_links_current_committed_document():
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _model, _document_id):
            return SimpleNamespace(
                id="document-1",
                crew_member_id="crew-1",
                classification="certificate",
                extraction_status="extracted",
                extracted_data={"certificate_type": "STCW"},
                extraction_confidence={"certificate_type": 0.9},
            )

    certification = MagicMock()
    certification.link_extracted_certificate = AsyncMock()
    factory = MagicMock(return_value=_Session())

    with (
        patch("app.database.get_session_factory", return_value=factory),
        patch("app.services.crew.certification_service", certification),
        patch("app.database.dispose_engine", new=AsyncMock()),
    ):
        result = reconcile_certificate_projection.run("document-1")

    assert result == {"document_id": "document-1", "status": "reconciled"}
    certification.link_extracted_certificate.assert_awaited_once_with(
        crew_id="crew-1",
        document_id="document-1",
        extracted_data={"certificate_type": "STCW"},
        confidence={"certificate_type": 0.9},
        expected_extracted_data={"certificate_type": "STCW"},
    )
