"""Tests for webhook-driven removal of records deleted inside Dropbox."""
import uuid

import pytest
from sqlalchemy import select

from app.api.dropbox import process_dropbox_deletion
from app.database import get_session_factory
from app.models import CrewMember, Document as DocumentModel


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
async def test_deletion_removes_document_record():
    """A file deleted in Dropbox drops the matching row."""
    crew_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    path = f"/hydenlyne/{crew_id}/documents/cv/{doc_id}_deleted.pdf"
    await _make_document(crew_id, doc_id, path)

    # Regression guard: this path once raised NameError because the upload
    # service was referenced without being imported.
    await process_dropbox_deletion(path)

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(DocumentModel).where(DocumentModel.id == doc_id)
        )
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
        result = await session.execute(
            select(DocumentModel).where(DocumentModel.id == doc_id)
        )
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
        result = await session.execute(
            select(DocumentModel).where(DocumentModel.id == doc_id)
        )
        assert result.scalar_one_or_none() is not None
