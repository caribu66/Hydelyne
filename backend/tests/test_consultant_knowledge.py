from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.consultant_knowledge import consultant_knowledge_service


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    def __init__(self, current):
        self.current = current

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def execute(self, _statement):
        return _Result(self.current)


def _session_factory(current):
    return lambda: _Session(current)


@pytest.mark.asyncio
async def test_meilisearch_indexing_reloads_latest_profile_before_write():
    stale_caller_object = SimpleNamespace(
        id="crew-1",
        full_name="Old Name",
        publication_status="approved",
    )
    latest_source_row = SimpleNamespace(
        id="crew-1",
        full_name="New Name",
        nationality=None,
        country_of_residence=None,
        availability_status="available",
        tags=[],
        gender=None,
        languages=None,
        flying_point=None,
        education=None,
        geographical_experience=None,
        systems_experience=None,
        training_qualifications=None,
        professional_summary=None,
        publication_status="approved",
    )
    index = AsyncMock(return_value={"task_uid": 1})

    with (
        patch("app.database.get_session_factory", return_value=_session_factory(latest_source_row)),
        patch(
            "app.services.consultant_knowledge.meilisearch_client.index_crew_member",
            index,
        ),
    ):
        result = await consultant_knowledge_service.index_crew_member(stale_caller_object)

    assert result is True
    indexed = index.await_args.args[0]
    assert indexed["full_name"] == "New Name"


@pytest.mark.asyncio
async def test_meilisearch_indexing_corrects_profile_changed_during_write():
    first_source_row = SimpleNamespace(
        id="crew-1",
        full_name="Old Name",
        nationality=None,
        country_of_residence=None,
        availability_status="available",
        tags=[],
        gender=None,
        languages=None,
        flying_point=None,
        education=None,
        geographical_experience=None,
        systems_experience=None,
        training_qualifications=None,
        professional_summary=None,
        publication_status="approved",
    )
    latest_source_row = SimpleNamespace(**{**vars(first_source_row), "full_name": "New Name"})
    index = AsyncMock(side_effect=[{"task_uid": 1}, {"task_uid": 2}])

    class _ChangingSession:
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def execute(self, _statement):
            self.calls += 1
            return _Result(first_source_row if self.calls == 1 else latest_source_row)

    changing_session = _ChangingSession()
    with (
        patch("app.database.get_session_factory", return_value=lambda: changing_session),
        patch(
            "app.services.consultant_knowledge.meilisearch_client.index_crew_member",
            index,
        ),
    ):
        result = await consultant_knowledge_service.index_crew_member(first_source_row)

    assert result is True
    assert [call.args[0]["full_name"] for call in index.await_args_list] == [
        "Old Name",
        "New Name",
    ]


@pytest.mark.asyncio
async def test_meilisearch_does_not_index_staff_accounts():
    staff_source_row = SimpleNamespace(
        id="staff-1",
        full_name="Staff Account",
        publication_status="approved",
        role="staff",
        password_hash=None,
    )
    index = AsyncMock()
    delete = AsyncMock(return_value=True)

    with (
        patch("app.database.get_session_factory", return_value=_session_factory(staff_source_row)),
        patch("app.services.consultant_knowledge.meilisearch_client.index_crew_member", index),
        patch("app.services.consultant_knowledge.meilisearch_client.delete_crew_member", delete),
    ):
        result = await consultant_knowledge_service.index_crew_member(staff_source_row)

    assert result is True
    index.assert_not_awaited()
    delete.assert_awaited_once_with("staff-1")


@pytest.mark.asyncio
async def test_meilisearch_removal_restores_profile_approved_during_delete():
    approved_source_row = SimpleNamespace(
        id="crew-1",
        full_name="Reapproved Name",
        nationality=None,
        country_of_residence=None,
        availability_status="available",
        tags=[],
        gender=None,
        languages=None,
        flying_point=None,
        education=None,
        geographical_experience=None,
        systems_experience=None,
        training_qualifications=None,
        professional_summary=None,
        publication_status="approved",
    )
    delete = AsyncMock(return_value=True)
    index = AsyncMock(return_value={"task_uid": 2})

    with (
        patch(
            "app.database.get_session_factory", return_value=_session_factory(approved_source_row)
        ),
        patch(
            "app.services.consultant_knowledge.meilisearch_client.delete_crew_member",
            delete,
        ),
        patch(
            "app.services.consultant_knowledge.meilisearch_client.index_crew_member",
            index,
        ),
    ):
        result = await consultant_knowledge_service.remove_from_index("crew-1")

    assert result is True
    delete.assert_awaited_once_with("crew-1")
    index.assert_awaited_once()
    assert index.await_args.args[0]["full_name"] == "Reapproved Name"


@pytest.mark.asyncio
async def test_document_projection_is_written_after_successful_extraction():
    document = SimpleNamespace(
        id="document-1",
        crew_member_id=None,
        file_name="certificate.pdf",
        file_type="pdf",
        file_size=12,
        classification="certificate",
        extraction_status="extracted",
        extracted_data={"certificate_type": "STCW"},
        uploaded_by="admin",
        version_number=1,
    )
    index = AsyncMock(return_value={"task_uid": 1})

    with (
        patch("app.database.get_session_factory", return_value=_session_factory(document)),
        patch(
            "app.services.consultant_knowledge.meilisearch_client.index_document",
            index,
        ),
    ):
        result = await consultant_knowledge_service.reconcile_document_index(document.id)

    assert result is True
    index.assert_awaited_once()
    assert index.await_args.args[0]["id"] == document.id
    assert "extracted_data" not in index.await_args.args[0]


@pytest.mark.asyncio
async def test_document_removal_reindexes_if_approval_races_delete():
    approved_document = SimpleNamespace(
        id="document-1",
        crew_member_id=None,
        file_name="certificate.pdf",
        file_type="pdf",
        file_size=12,
        classification="certificate",
        extraction_status="approved",
        extracted_data={"certificate_type": "STCW"},
        uploaded_by="admin",
        version_number=1,
    )

    class _ChangingSession:
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def execute(self, _statement):
            self.calls += 1
            return _Result(None if self.calls == 1 else approved_document)

    delete = AsyncMock(return_value=True)
    index = AsyncMock(return_value={"task_uid": 1})
    session = _ChangingSession()

    with (
        patch("app.database.get_session_factory", return_value=lambda: session),
        patch("app.services.consultant_knowledge.meilisearch_client.delete_document", delete),
        patch("app.services.consultant_knowledge.meilisearch_client.index_document", index),
    ):
        result = await consultant_knowledge_service.reconcile_document_index("document-1")

    assert result is True
    delete.assert_awaited_once_with("document-1")
    index.assert_awaited_once()
