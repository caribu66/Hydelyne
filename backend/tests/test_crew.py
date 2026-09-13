"""Test crew member GraphQL operations."""

import inspect
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import Certification, CrewMember, Document, Project
from app.services.crew import (
    PossibleDuplicateError,
    _availability_date_for_update,
    _counts_as_valid_certification,
    crew_service,
)

DELETE_CREW_MUTATION = """
mutation DeleteCrewMember($id: String!) {
    deleteCrewMember(id: $id)
}
"""

CREATE_CREW_MUTATION = """
mutation CreateCrewMember($fullName: String!, $email: String, $phone: String, $nationality: String) {
    createCrewMember(fullName: $fullName, email: $email, phone: $phone, nationality: $nationality) {
        id
        fullName
        email
        phone
        nationality
        availabilityStatus
    }
}
"""

GET_CREW_QUERY = """
query GetCrewMember($id: String!) {
    crewMember(id: $id) {
        id
        fullName
        email
        phone
        nationality
    }
}
"""


def test_valid_certification_count_uses_verified_expiry_window():
    reference_date = date(2026, 9, 13)

    assert _counts_as_valid_certification(
        date(2027, 1, 1), "verified", reference_date
    ) is True
    assert _counts_as_valid_certification(
        date(2026, 9, 20), "verified", reference_date
    ) is False
    assert _counts_as_valid_certification(None, "verified", reference_date) is True


@pytest.mark.asyncio
async def test_staff_role_change_removes_search_projection_after_commit(monkeypatch):
    """Role promotion must revoke derived contractor visibility."""

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    crew = SimpleNamespace(
        id="crew-1",
        role="user",
        documents=[SimpleNamespace(id="document-1")],
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: crew)
        ),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.crew.get_session_factory",
        lambda: lambda: SessionContext(),
    )
    monkeypatch.setattr(
        "app.services.crew._reload_crew_with_relations",
        AsyncMock(return_value=crew),
    )
    remove_from_index = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.services.crew.consultant_knowledge_service.remove_from_index",
        remove_from_index,
    )
    clear_cache = AsyncMock(return_value=True)
    monkeypatch.setattr("app.services.crew.cache_service.delete", clear_cache)
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(ENABLE_SEMANTIC_SEARCH=False),
    )

    result = await crew_service.set_staff_role("crew-1", enabled=True)

    assert result is crew
    assert crew.role == "staff"
    session.commit.assert_awaited_once()
    remove_from_index.assert_awaited_once_with("crew-1")
    assert clear_cache.await_count == 2


@pytest.mark.asyncio
async def test_update_availability_ignores_login_account_rows(monkeypatch):
    account = SimpleNamespace(password_hash="hashed", role="staff")

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args):
            return None

    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: account)
        ),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.crew.get_session_factory",
        lambda: lambda: SessionContext(),
    )

    result = await crew_service.update_availability("staff-1", "available")

    assert result is None
    assert not hasattr(account, "availability_status")
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_crew_member_rejects_login_account_rows(monkeypatch):
    account = SimpleNamespace(password_hash="hashed", role="staff")

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args):
            return None

    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: account)
        )
    )
    monkeypatch.setattr(
        "app.services.crew.get_session_factory",
        lambda: lambda: SessionContext(),
    )

    with pytest.raises(ValueError, match="Crew member staff-1 not found"):
        await crew_service.update_crew_member("staff-1", {"full_name": "Changed"})


@pytest.mark.asyncio
async def test_compliance_status_excludes_login_account_certifications(monkeypatch):
    """Compliance aggregates must be contractor-scoped even for admins."""

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    account = SimpleNamespace(password_hash="hashed", role="staff")
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: account)
        )
    )
    monkeypatch.setattr(
        "app.services.crew.get_session_factory",
        lambda: lambda: SessionContext(),
    )

    result = await crew_service.get_compliance_status("staff-1")

    assert result == {
        "total": 0,
        "valid": 0,
        "expiring_soon": 0,
        "expired": 0,
        "pending_verification": 0,
    }
    session.execute.assert_awaited_once()

LIST_CREW_QUERY = """
query ListCrewMembers {
    crewMembers(limit: 10, offset: 0) {
        id
        fullName
        email
    }
}
"""

UPDATE_CREW_MUTATION = """
mutation UpdateCrewMember($id: String!, $fullName: String, $phone: String) {
    updateCrewMember(id: $id, fullName: $fullName, phone: $phone) {
        id
        fullName
        phone
    }
}
"""

RETIRED_CV_MUTATION = """
mutation UploadCvAndExtract($crewId: String!, $fileName: String!, $fileType: String!, $fileSize: Int!) {
    uploadCvAndExtract(crewId: $crewId, fileName: $fileName, fileType: $fileType, fileSize: $fileSize) {
        documentId
    }
}
"""


def test_availability_date_only_exists_for_on_assignment() -> None:
    assigned_date = date(2026, 9, 13)
    assert _availability_date_for_update("available", assigned_date) is None
    assert _availability_date_for_update("unavailable", assigned_date) is None
    assert _availability_date_for_update("on_assignment", assigned_date) == assigned_date
    with pytest.raises(ValueError, match="available_date is required"):
        _availability_date_for_update("on_assignment", None)


def test_create_crew_member_requires_an_explicit_publication_decision() -> None:
    from app.services.crew import CrewService

    parameter = inspect.signature(CrewService.create_crew_member).parameters["as_draft"]
    assert parameter.default is inspect.Parameter.empty


@pytest.mark.asyncio
async def test_create_crew_member(client):
    response = await client.post(
        "/graphql",
        json={
            "query": CREATE_CREW_MUTATION,
            "variables": {
                "fullName": "John Smith",
                "email": "john.smith@example.com",
                "phone": "+44 1234 567890",
                "nationality": "British",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]["createCrewMember"]
    assert data["fullName"] == "John Smith"
    assert data["email"] == "john.smith@example.com"
    assert data["availabilityStatus"] == "available"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_draft_duplicate_detection_trims_stored_identity_fields(db_session):
    existing = CrewMember(
        id=str(uuid.uuid4()),
        full_name="  Stored Person  ",
        email="  stored@example.com  ",
    )
    db_session.add(existing)
    await db_session.commit()

    with pytest.raises(PossibleDuplicateError):
        await crew_service.create_crew_member(
            CrewMember(
                full_name="Stored Person",
                email="STORED@example.com",
            ),
            as_draft=True,
            submitted_by="staff-1",
        )


@pytest.mark.asyncio
async def test_get_crew_member(client):
    create_response = await client.post(
        "/graphql",
        json={
            "query": CREATE_CREW_MUTATION,
            "variables": {"fullName": "Jane Doe", "email": "jane@example.com"},
        },
    )
    crew_id = create_response.json()["data"]["createCrewMember"]["id"]

    response = await client.post(
        "/graphql",
        json={"query": GET_CREW_QUERY, "variables": {"id": crew_id}},
    )
    assert response.status_code == 200
    data = response.json()["data"]["crewMember"]
    assert data["fullName"] == "Jane Doe"
    assert data["email"] == "jane@example.com"


@pytest.mark.asyncio
async def test_update_crew_member(client):
    create_response = await client.post(
        "/graphql",
        json={
            "query": CREATE_CREW_MUTATION,
            "variables": {"fullName": "Alex Storm", "email": "alex@example.com"},
        },
    )
    crew_id = create_response.json()["data"]["createCrewMember"]["id"]

    response = await client.post(
        "/graphql",
        json={
            "query": UPDATE_CREW_MUTATION,
            "variables": {"id": crew_id, "fullName": "Alex J. Storm", "phone": "+44 7000 000000"},
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]["updateCrewMember"]
    assert data["fullName"] == "Alex J. Storm"
    assert data["phone"] == "+44 7000 000000"


@pytest.mark.asyncio
async def test_list_crew_members(client):
    response = await client.post(
        "/graphql",
        json={"query": LIST_CREW_QUERY},
    )
    assert response.status_code == 200
    data = response.json()["data"]["crewMembers"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_crew_members_prioritizes_newest_records(db_session):
    older = CrewMember(
        id="crew-older",
        full_name="Older Specialist",
        email="older@example.com",
        created_at=datetime(2026, 1, 1),
    )
    newest = CrewMember(
        id="crew-newest",
        full_name="Newest Specialist",
        email="newest@example.com",
        created_at=datetime(2026, 1, 2),
    )
    db_session.add_all([older, newest])
    await db_session.commit()

    records = await crew_service.list_crew_members(limit=1)

    assert [record.id for record in records] == ["crew-newest"]


@pytest.mark.asyncio
async def test_list_crew_members_excludes_staff_and_admin_accounts(db_session):
    db_session.add_all(
        [
            CrewMember(id="contractor-user", full_name="Contractor User", role="user"),
            CrewMember(id="staff-account", full_name="Staff Account", role="staff"),
            CrewMember(id="admin-account", full_name="Admin Account", role="admin"),
            CrewMember(
                id="demoted-login-account",
                full_name="Demoted Login Account",
                role="user",
                password_hash="stored-password-hash",
            ),
            CrewMember(id="legacy-null-role", full_name="Legacy Null Role", role=None),
        ]
    )
    await db_session.commit()

    records = await crew_service.list_crew_members(limit=100)

    assert {record.id for record in records} == {"contractor-user", "legacy-null-role"}


@pytest.mark.asyncio
async def test_compliance_status_does_not_count_unverified_valid_certification(
    db_session, monkeypatch
):
    crew = CrewMember(id="compliance-aggregate-crew", full_name="Compliance Aggregate")
    db_session.add(crew)
    await db_session.flush()
    db_session.add(
        Certification(
            crew_member_id=crew.id,
            cert_type="BOSIET",
            status="valid",
            verification_status="unverified",
        )
    )
    await db_session.commit()

    async def uncached(_key, fetch, *, ttl):
        return await fetch()

    monkeypatch.setattr("app.services.crew.cache_service.get_or_set", uncached)

    result = await crew_service.get_compliance_status(crew.id)

    assert result["total"] == 1
    assert result["valid"] == 0
    assert result["pending_verification"] == 1


@pytest.mark.asyncio
async def test_compliance_status_uses_expiry_date_for_valid_count(db_session, monkeypatch):
    crew = CrewMember(id="compliance-stale-valid-crew", full_name="Stale Valid Status")
    db_session.add(crew)
    await db_session.flush()
    db_session.add_all(
        [
            Certification(
                crew_member_id=crew.id,
                cert_type="BOSIET",
                status="valid",
                verification_status="verified",
                expiry_date=date.today() + timedelta(days=7),
            ),
            Certification(
                crew_member_id=crew.id,
                cert_type="HUET",
                status="expired",
                verification_status="verified",
                expiry_date=date.today() + timedelta(days=120),
            ),
        ]
    )
    await db_session.commit()

    async def uncached(_key, fetch, *, ttl):
        return await fetch()

    monkeypatch.setattr("app.services.crew.cache_service.get_or_set", uncached)

    result = await crew_service.get_compliance_status(crew.id)

    assert result["valid"] == 1
    assert result["expiring_soon"] == 1
    assert result["expired"] == 0


@pytest.mark.asyncio
async def test_compliance_status_counts_legacy_null_certification_states(
    db_session, monkeypatch
):
    """Legacy nullable certification states remain visible as pending evidence."""
    crew = CrewMember(id="compliance-null-crew", full_name="Legacy Compliance")
    db_session.add(crew)
    await db_session.flush()
    db_session.add(
        Certification(
            crew_member_id=crew.id,
            cert_type="BOSIET",
            status=None,
            verification_status=None,
        )
    )
    await db_session.commit()

    async def uncached(_key, fetch, *, ttl):
        return await fetch()

    monkeypatch.setattr("app.services.crew.cache_service.get_or_set", uncached)

    result = await crew_service.get_compliance_status(crew.id)

    assert result["total"] == 1
    assert result["pending_verification"] == 1


@pytest.mark.asyncio
async def test_compliance_status_does_not_count_unverified_expiry_states(db_session, monkeypatch):
    crew = CrewMember(id="compliance-expiry-crew", full_name="Pending Expiry")
    db_session.add(crew)
    await db_session.flush()
    db_session.add_all(
        [
            Certification(
                crew_member_id=crew.id,
                cert_type="BOSIET",
                status="expiring_soon",
                verification_status="unverified",
                expiry_date=date.today() + timedelta(days=7),
            ),
            Certification(
                crew_member_id=crew.id,
                cert_type="HUET",
                status="expired",
                verification_status="unverified",
                expiry_date=date.today() - timedelta(days=7),
            ),
        ]
    )
    await db_session.commit()

    async def uncached(_key, fetch, *, ttl):
        return await fetch()

    monkeypatch.setattr("app.services.crew.cache_service.get_or_set", uncached)

    result = await crew_service.get_compliance_status(crew.id)

    assert result["expiring_soon"] == 0
    assert result["expired"] == 0
    assert result["pending_verification"] == 2


@pytest.mark.asyncio
async def test_staff_account_listing_includes_unpublished_profiles(db_session):
    db_session.add_all(
        [
            CrewMember(
                id="account-approved",
                full_name="Approved Account",
                role="staff",
                password_hash="legacy-hash",
            ),
            CrewMember(
                id="account-draft",
                full_name="Draft Account",
                publication_status="draft",
                role="staff",
                password_hash="legacy-hash",
            ),
            CrewMember(
                id="account-rejected",
                full_name="Rejected Account",
                publication_status="rejected",
                role="staff",
                password_hash="legacy-hash",
            ),
            CrewMember(id="contractor-row", full_name="Contractor Row", role="user"),
        ]
    )
    await db_session.commit()

    records = await crew_service.list_staff_accounts(limit=100)

    assert {record.id for record in records} >= {
        "account-approved",
        "account-draft",
        "account-rejected",
    }
    assert "contractor-row" not in {record.id for record in records}


@pytest.mark.asyncio
async def test_retired_cv_metadata_mutation_does_not_claim_success(client):
    response = await client.post(
        "/graphql",
        json={
            "query": RETIRED_CV_MUTATION,
            "variables": {
                "crewId": "test-crew-id",
                "fileName": "candidate.pdf",
                "fileType": "application/pdf",
                "fileSize": 42,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] is None
    assert payload["errors"][0]["extensions"]["code"] == "BAD_USER_INPUT"


@pytest.mark.asyncio
async def test_delete_crew_member_queues_failed_dropbox_cleanup_after_metadata_delete(
    client, db_session, monkeypatch
):
    """A failed remote cleanup must not undo the source-of-truth deletion."""
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Has Dropbox Doc", role="user")
    db_session.add(crew)
    await db_session.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        crew_member_id=crew.id,
        file_name="contract.pdf",
        file_type="application/pdf",
        file_size=10,
        storage_path="/hydenlyne/crew/documents/contract.pdf",
        storage_type="dropbox",
        dropbox_path="/hydenlyne/crew/documents/contract.pdf",
    )
    db_session.add(doc)
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.upload.document_upload_service.delete_from_dropbox",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr("app.services.upload.document_upload_service.delete_file", MagicMock())
    queue_cleanup = MagicMock()
    monkeypatch.setattr("app.tasks.document_tasks.queue_orphaned_upload_cleanup", queue_cleanup)

    response = await client.post(
        "/graphql",
        json={"query": DELETE_CREW_MUTATION, "variables": {"id": crew.id}},
    )
    body = response.json()
    assert body["data"]["deleteCrewMember"] is True
    assert "errors" not in body

    assert await crew_service.get_crew_member(crew.id) is None
    queue_cleanup.assert_called_once_with("dropbox", doc.dropbox_path)


@pytest.mark.asyncio
async def test_delete_crew_member_removes_legacy_project_assignment(client, db_session):
    crew = CrewMember(id=str(uuid.uuid4()), full_name="Assigned Crew", role="user")
    other = CrewMember(id=str(uuid.uuid4()), full_name="Remaining Crew", role="user")
    project = Project(
        id=str(uuid.uuid4()),
        client_name="Client",
        project_name="Project",
        project_type="survey",
        crew_assigned=[crew.id, other.id],
    )
    db_session.add_all([crew, other, project])
    await db_session.commit()

    response = await client.post(
        "/graphql", json={"query": DELETE_CREW_MUTATION, "variables": {"id": crew.id}}
    )
    assert response.json()["data"]["deleteCrewMember"] is True

    await db_session.refresh(project)
    assert project.crew_assigned == [other.id]


@pytest.mark.asyncio
async def test_admin_cannot_delete_own_account(client):
    """Characterization test: the resolver has an explicit self-delete guard
    with zero prior test coverage. conftest.py's default test identity has a
    fixed id, so this deletes that exact id to hit the guard."""
    from tests.conftest import _dummy_user

    response = await client.post(
        "/graphql",
        json={"query": DELETE_CREW_MUTATION, "variables": {"id": _dummy_user.id}},
    )
    body = response.json()
    assert body["data"] is None
    assert "cannot delete your own administrator account" in body["errors"][0]["message"]


@pytest.mark.asyncio
async def test_staff_submitter_cannot_access_rejected_profile(db_session):
    rejected = CrewMember(
        id=str(uuid.uuid4()),
        full_name="Rejected Submission",
        publication_status="rejected",
        submitted_by="staff-1",
    )
    db_session.add(rejected)
    await db_session.commit()

    assert (
        await crew_service.can_access_profile(
            rejected.id,
            actor_id="staff-1",
            actor_role="staff",
        )
        is False
    )
