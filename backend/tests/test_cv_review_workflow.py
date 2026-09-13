"""Security and publication regressions for reviewed CV ingestion."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import get_session_factory
from app.models import CrewMember, CVReview, Document
from app.services.crew import crew_service
from app.services.cv_processing import cv_processing_service
from app.services.cv_review import (
    _repair_crew_projection,
    _repair_document_projection,
    _repair_document_vector,
    cv_review_service,
)
from app.services.document_service import document_service


class _CVReviewResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        if self.value is None:
            raise AssertionError("Expected a CV review result")
        return self.value


class _CVReviewSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_cv_approval_rejects_login_account_owner(monkeypatch):
    review = SimpleNamespace(
        id="review-1",
        crew_member_id="staff-1",
        document_id="document-1",
        status="awaiting_review",
    )
    document = SimpleNamespace(crew_member_id="staff-1", extraction_status="awaiting_review")
    account = SimpleNamespace(password_hash="hashed", role="staff")
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _CVReviewResult(review),
                _CVReviewResult(document),
                _CVReviewResult(review),
                _CVReviewResult(account),
            ]
        )
    )
    monkeypatch.setattr(
        "app.services.cv_review.get_session_factory",
        lambda: lambda: _CVReviewSessionContext(session),
    )

    with pytest.raises(ValueError, match="Crew member not found"):
        await cv_review_service.approve(
            "review-1", approved_data={"full_name": "Account"}, reviewer_id="admin-1"
        )


@pytest.mark.asyncio
async def test_cv_rejection_rejects_document_owner_mismatch(monkeypatch):
    review = SimpleNamespace(
        id="review-1",
        crew_member_id="crew-1",
        document_id="document-1",
        status="awaiting_review",
    )
    document = SimpleNamespace(crew_member_id="crew-2", extraction_status="awaiting_review")
    contractor = SimpleNamespace(password_hash=None, role=None)
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _CVReviewResult(review),
                _CVReviewResult(document),
                _CVReviewResult(review),
                _CVReviewResult(contractor),
            ]
        )
    )
    monkeypatch.setattr(
        "app.services.cv_review.get_session_factory",
        lambda: lambda: _CVReviewSessionContext(session),
    )

    with pytest.raises(ValueError, match="does not belong"):
        await cv_review_service.reject("review-1", reviewer_id="admin-1", note="Mismatch")


@pytest.mark.asyncio
async def test_direct_cv_processing_locks_and_rejects_login_account(monkeypatch):
    account = SimpleNamespace(password_hash="hashed", role="staff")
    session = SimpleNamespace(execute=AsyncMock(return_value=_CVReviewResult(account)))
    monkeypatch.setattr(
        "app.services.cv_processing.get_session_factory",
        lambda: lambda: _CVReviewSessionContext(session),
    )

    with pytest.raises(ValueError, match="Crew member not found"):
        await cv_processing_service.process_cv_extraction(
            "staff-1", {"full_name": "Account"}
        )

    assert "FOR UPDATE" in str(session.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_cv_review_approval_rejects_non_object_data_before_database_access():
    with pytest.raises(ValueError, match="JSON object"):
        await cv_review_service.approve(
            "review-1",
            approved_data=[],
            reviewer_id="admin-1",
        )


@pytest.mark.asyncio
async def test_cv_reprocessing_replaces_stale_review_proposal(db_session):
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    crew = CrewMember(id=crew_id, full_name="CV Review Crew", publication_status="draft")
    document = Document(
        id=document_id,
        crew_member_id=crew_id,
        file_name="current-cv.pdf",
        file_type="pdf",
        file_size=10,
        storage_type="local",
        storage_path=f"/tmp/{document_id}.pdf",
        classification="cv",
        extraction_status="pending",
        extracted_data=None,
    )
    db_session.add_all([crew, document])
    await db_session.flush()
    db_session.add(
        CVReview(
            id=review_id,
            document_id=document_id,
            crew_member_id=crew_id,
            status="awaiting_review",
            proposed_data={"full_name": "Old Name", "nationality": "Stale Country"},
            submitted_by="staff-1",
        )
    )
    await db_session.commit()

    current_result = {"full_name": "Current Name", "confidence": {"all": 0.95}}
    with (
        patch(
            "app.services.document_service.document_upload_service.get_file_async",
            new=AsyncMock(return_value=b"%PDF current"),
        ),
        patch(
            "app.services.document_service.text_extraction_service.extract_text",
            new=AsyncMock(return_value="Current CV text"),
        ),
        patch(
            "app.services.cv_processing.CVProcessingService.extract_cv_deterministically",
            return_value=current_result,
        ),
        patch(
            "app.services.document_service.extraction_service.determine_review_status",
            return_value=("awaiting_review", ["all"]),
        ),
        patch(
            "app.services.consultant_knowledge.consultant_knowledge_service.reconcile_document_index",
            new=AsyncMock(return_value=True),
        ),
        patch("app.services.document_service._log_extraction_best_effort", new=AsyncMock()),
    ):
        result = await document_service.process_document(document_id)

    assert result["status"] == "awaiting_review"
    review = (
        await db_session.execute(select(CVReview).where(CVReview.id == review_id))
    ).scalar_one()
    assert review.proposed_data == current_result


@pytest.mark.asyncio
async def test_cv_projection_repairs_queue_after_provider_exception():
    crew = CrewMember(id="crew-1", publication_status="approved")
    with (
        patch(
            "app.services.cv_review.consultant_knowledge_service.index_crew_member",
            new=AsyncMock(side_effect=RuntimeError("search unavailable")),
        ),
        patch("app.tasks.document_tasks.queue_crew_projection_reconcile") as queue_crew,
        patch(
            "app.services.cv_review.consultant_knowledge_service.reconcile_document_index",
            new=AsyncMock(side_effect=RuntimeError("search unavailable")),
        ),
        patch("app.tasks.document_tasks.queue_document_search_reconcile") as queue_document,
    ):
        await _repair_crew_projection(crew)
        await _repair_document_projection("document-1")

    queue_crew.assert_called_once_with("crew-1")
    queue_document.assert_called_once_with("document-1")


@pytest.mark.asyncio
async def test_cv_vector_repair_queues_after_provider_exception():
    settings = get_settings()
    previous = settings.ENABLE_SEMANTIC_SEARCH
    settings.ENABLE_SEMANTIC_SEARCH = True
    try:
        with (
            patch(
                "app.services.qdrant.qdrant_service.delete_document",
                new=AsyncMock(side_effect=RuntimeError("qdrant unavailable")),
            ),
            patch("app.tasks.document_tasks.queue_document_projection_cleanup") as queue_cleanup,
        ):
            await _repair_document_vector("document-1")
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = previous

    queue_cleanup.assert_called_once_with("document-1")


@pytest.mark.asyncio
async def test_cv_approval_rejects_review_when_document_revision_is_pending(db_session):
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id,
            full_name="Pending Revision Crew",
            publication_status="draft",
        )
    )
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew_id,
            file_name="revised-cv.pdf",
            file_type="pdf",
            file_size=1,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="cv",
            extraction_status="pending",
        )
    )
    await db_session.flush()
    db_session.add(
        CVReview(
            id=review_id,
            document_id=document_id,
            crew_member_id=crew_id,
            status="awaiting_review",
            submitted_by="staff-1",
        )
    )
    await db_session.commit()

    with pytest.raises(ValueError, match="no longer awaiting approval"):
        await cv_review_service.approve(
            review_id,
            approved_data={"full_name": "Stale approval"},
            reviewer_id="admin-1",
        )


@pytest.mark.asyncio
async def test_draft_specialist_is_not_searchable_until_approved():
    factory = get_session_factory()
    async with factory() as session:
        draft = CrewMember(
            id=str(uuid.uuid4()),
            full_name="Hidden Draft Specialist",
            publication_status="draft",
            submitted_by="staff-1",
        )
        approved = CrewMember(id=str(uuid.uuid4()), full_name="Approved Specialist")
        session.add_all([draft, approved])
        await session.commit()

    visible = await crew_service.list_crew_members()
    assert [crew.full_name for crew in visible] == ["Approved Specialist"]


@pytest.mark.asyncio
async def test_staff_can_create_cv_draft_but_not_publish_directly(client, monkeypatch):
    staff = CrewMember(
        id=str(uuid.uuid4()), full_name="Staff Member", email="staff@example.com", role="staff"
    )
    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )
    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation Create($name: String!) {
                    createCrewMember(fullName: $name, cvSubmission: true) {
                        id publicationStatus
                    }
                }
            """,
            "variables": {"name": "New CV Specialist"},
        },
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["createCrewMember"]["publicationStatus"] == "draft"
    assert await crew_service.list_crew_members(search="New CV Specialist") == []

    approval = await client.post(
        "/graphql",
        json={
            "query": """
                mutation { approveCvReview(reviewId: "x", approvedData: "{}") }
            """
        },
    )
    assert approval.json()["errors"][0]["extensions"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_staff_cannot_view_another_staff_members_draft(client, monkeypatch):
    staff = CrewMember(
        id=str(uuid.uuid4()),
        full_name="First Staff Member",
        email="first@example.com",
        role="staff",
    )
    other_staff_id = str(uuid.uuid4())
    draft_id = str(uuid.uuid4())
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            CrewMember(
                id=draft_id,
                full_name="Other Staff Draft",
                publication_status="draft",
                submitted_by=other_staff_id,
            )
        )
        await session.commit()

    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )
    response = await client.post(
        "/graphql",
        json={"query": f'query {{ crewMember(id: "{draft_id}") {{ id }} }}'},
    )

    assert response.json() == {"data": {"crewMember": None}}


@pytest.mark.asyncio
async def test_staff_cannot_view_own_rejected_profile(client, monkeypatch):
    staff_id = str(uuid.uuid4())
    staff = CrewMember(id=staff_id, full_name="Rejecting Staff", role="staff")
    rejected_id = str(uuid.uuid4())
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            CrewMember(
                id=rejected_id,
                full_name="Rejected Own Submission",
                publication_status="rejected",
                submitted_by=staff_id,
            )
        )
        await session.commit()

    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )
    response = await client.post(
        "/graphql",
        json={"query": f'query {{ crewMember(id: "{rejected_id}") {{ id }} }}'},
    )

    assert response.json() == {"data": {"crewMember": None}}


@pytest.mark.asyncio
async def test_staff_review_queue_contains_only_their_submissions(client, monkeypatch):
    staff_id = str(uuid.uuid4())
    other_staff_id = str(uuid.uuid4())
    staff = CrewMember(id=staff_id, full_name="Queue Staff", role="staff")
    factory = get_session_factory()
    review_ids: list[str] = []
    async with factory() as session:
        for submitter in (staff_id, other_staff_id):
            crew_id = str(uuid.uuid4())
            document_id = str(uuid.uuid4())
            review_id = str(uuid.uuid4())
            session.add(
                CrewMember(
                    id=crew_id,
                    full_name="Queued Draft",
                    publication_status="draft",
                    submitted_by=submitter,
                )
            )
            session.add(
                Document(
                    id=document_id,
                    crew_member_id=crew_id,
                    file_name="cv.pdf",
                    file_type="pdf",
                    file_size=100,
                    storage_type="local",
                    storage_path=f"/tmp/{document_id}.pdf",
                    classification="cv",
                    extraction_status="awaiting_review",
                )
            )
            # Parent-first flush: Document/CVReview are FK-linked with no ORM
            # relationship, so a combined flush misorders on PostgreSQL.
            await session.flush()
            session.add(
                CVReview(
                    id=review_id,
                    document_id=document_id,
                    crew_member_id=crew_id,
                    status="awaiting_review",
                    submitted_by=submitter,
                )
            )
            review_ids.append(review_id)
        await session.commit()

    monkeypatch.setattr(
        "app.services.crew.auth_service.get_user_from_token", AsyncMock(return_value=staff)
    )
    response = await client.post(
        "/graphql",
        json={
            "query": """
                query {
                    cvReviews(limit: 10, offset: 0) {
                        id proposedData approvedData reviewNote
                    }
                }
            """
        },
    )

    assert response.json()["data"]["cvReviews"] == [
        {
            "id": review_ids[0],
            "proposedData": None,
            "approvedData": None,
            "reviewNote": None,
        }
    ]


@pytest.mark.asyncio
async def test_duplicate_draft_is_blocked(client):
    factory = get_session_factory()
    async with factory() as session:
        session.add(CrewMember(id=str(uuid.uuid4()), full_name="Existing Person"))
        await session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation { createCrewMember(fullName: "Existing Person", cvSubmission: true) { id } }
            """
        },
    )
    error = response.json()["errors"][0]
    assert error["extensions"]["code"] == "POSSIBLE_DUPLICATE"


@pytest.mark.asyncio
async def test_admin_confirmed_distinct_cv_stays_draft_until_review(client):
    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation {
                    createCrewMember(
                        fullName: "Distinct CV Person",
                        cvSubmission: true,
                        confirmDistinct: true
                    ) { id publicationStatus }
                }
            """
        },
    )
    body = response.json()
    assert "errors" not in body, body
    assert body["data"]["createCrewMember"]["publicationStatus"] == "draft"


@pytest.mark.asyncio
async def test_admin_can_promote_an_existing_user_to_staff(client):
    user_id = str(uuid.uuid4())
    factory = get_session_factory()
    async with factory() as session:
        session.add(CrewMember(id=user_id, full_name="Existing User", role="user"))
        await session.commit()

    response = await client.post(
        "/graphql",
        json={
            "query": """
                mutation Promote($id: String!) {
                    setStaffRole(userId: $id, enabled: true) { id role }
                }
            """,
            "variables": {"id": user_id},
        },
    )

    assert response.json()["data"]["setStaffRole"] == {"id": user_id, "role": "staff"}


@pytest.mark.asyncio
async def test_admin_approval_publishes_exact_reviewed_data(client):
    factory = get_session_factory()
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    proposed = {"full_name": "Reviewed Specialist", "skills": ["Hydrography"]}
    async with factory() as session:
        session.add(
            CrewMember(
                id=crew_id,
                full_name="Pending CV import",
                email="operator@example.com",
                phone="+44 7000 111111",
                publication_status="draft",
                submitted_by="staff-1",
            )
        )
        session.add(
            Document(
                id=document_id,
                crew_member_id=crew_id,
                file_name="cv.pdf",
                file_type="pdf",
                file_size=100,
                storage_type="local",
                storage_path="/tmp/cv.pdf",
                classification="cv",
                extraction_status="awaiting_review",
            )
        )
        # Parent-first flush: Document/CVReview are FK-linked with no ORM
        # relationship, so a combined flush misorders on PostgreSQL.
        await session.flush()
        session.add(
            CVReview(
                id=review_id,
                document_id=document_id,
                crew_member_id=crew_id,
                status="awaiting_review",
                proposed_data=proposed,
                submitted_by="staff-1",
            )
        )
        await session.commit()

    settings = get_settings()
    previous_semantic_flag = settings.ENABLE_SEMANTIC_SEARCH
    settings.ENABLE_SEMANTIC_SEARCH = True
    try:
        with (
            patch(
                "app.services.cv_review.consultant_knowledge_service.index_crew_member",
                new=AsyncMock(),
            ),
            patch(
                "app.tasks.document_tasks.index_document_embeddings.delay",
                new=MagicMock(),
            ) as embedding_delay,
        ):
            response = await client.post(
                "/graphql",
                json={
                    "query": """
                        mutation Approve($id: String!, $data: String!) {
                            approveCvReview(reviewId: $id, approvedData: $data)
                        }
                    """,
                    "variables": {"id": review_id, "data": json.dumps(proposed)},
                },
            )
            embedding_delay.assert_called_once_with(document_id)
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = previous_semantic_flag

    assert response.json()["data"]["approveCvReview"] is True
    async with factory() as session:
        crew = (
            await session.execute(select(CrewMember).where(CrewMember.id == crew_id))
        ).scalar_one()
        review = (
            await session.execute(select(CVReview).where(CVReview.id == review_id))
        ).scalar_one()
        document = (
            await session.execute(select(Document).where(Document.id == document_id))
        ).scalar_one()
    assert crew.publication_status == "approved"
    assert crew.full_name == "Reviewed Specialist"
    assert crew.email == "operator@example.com"
    assert crew.phone == "+44 7000 111111"
    assert review.status == "approved"
    assert review.approved_data == proposed
    assert document.extraction_status == "approved"


@pytest.mark.asyncio
async def test_failed_approval_restores_an_existing_approved_profile():
    factory = get_session_factory()
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    async with factory() as session:
        session.add(
            CrewMember(
                id=crew_id,
                full_name="Original Approved Name",
                email="original@example.com",
                publication_status="approved",
            )
        )
        session.add(
            Document(
                id=document_id,
                crew_member_id=crew_id,
                file_name="replacement.pdf",
                file_type="pdf",
                file_size=100,
                storage_type="local",
                storage_path="/tmp/replacement.pdf",
                classification="cv",
                extraction_status="awaiting_review",
            )
        )
        # Parent-first flush: Document/CVReview are FK-linked with no ORM
        # relationship, so a combined flush misorders on PostgreSQL.
        await session.flush()
        session.add(
            CVReview(
                id=review_id,
                document_id=document_id,
                crew_member_id=crew_id,
                status="awaiting_review",
                prior_publication_status="approved",
                proposed_data={"full_name": "Replacement Name"},
                submitted_by="staff-1",
            )
        )
        await session.commit()

    with (
        patch(
            "app.services.cv_processing.CVProcessingService._create_certifications",
            new=AsyncMock(side_effect=RuntimeError("apply failed")),
        ),
        patch(
            "app.services.cv_review.consultant_knowledge_service.index_crew_member",
            new=AsyncMock(),
        ),
        patch(
            "app.services.cv_review.consultant_knowledge_service.remove_from_index",
            new=AsyncMock(),
        ),
        pytest.raises(RuntimeError, match="apply failed"),
    ):
        await cv_review_service.approve(
            review_id,
            approved_data={"full_name": "Replacement Name"},
            reviewer_id="admin-1",
        )

    async with factory() as session:
        crew = (
            await session.execute(select(CrewMember).where(CrewMember.id == crew_id))
        ).scalar_one()
        review = (
            await session.execute(select(CVReview).where(CVReview.id == review_id))
        ).scalar_one()
    assert crew.full_name == "Original Approved Name"
    assert crew.email == "original@example.com"
    assert crew.publication_status == "approved"
    assert review.status == "awaiting_review"


@pytest.mark.asyncio
async def test_rejecting_a_cv_update_keeps_the_existing_profile_published(client):
    factory = get_session_factory()
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    async with factory() as session:
        session.add(
            CrewMember(
                id=crew_id,
                full_name="Existing Published Contractor",
                publication_status="approved",
            )
        )
        session.add(
            Document(
                id=document_id,
                crew_member_id=crew_id,
                file_name="rejected-update.pdf",
                file_type="pdf",
                file_size=100,
                storage_type="local",
                storage_path="/tmp/rejected-update.pdf",
                classification="cv",
                extraction_status="awaiting_review",
            )
        )
        # Parent-first flush: Document/CVReview are FK-linked with no ORM
        # relationship, so a combined flush misorders on PostgreSQL.
        await session.flush()
        session.add(
            CVReview(
                id=review_id,
                document_id=document_id,
                crew_member_id=crew_id,
                status="awaiting_review",
                prior_publication_status="approved",
                proposed_data={"full_name": "Unaccepted Name"},
                submitted_by="staff-1",
            )
        )
        await session.commit()

    settings = get_settings()
    previous_semantic_flag = settings.ENABLE_SEMANTIC_SEARCH
    settings.ENABLE_SEMANTIC_SEARCH = True
    try:
        with (
            patch(
                "app.services.cv_review.consultant_knowledge_service.index_crew_member",
                new=AsyncMock(),
            ),
            patch(
                "app.services.qdrant.qdrant_service.delete_document",
                new=AsyncMock(),
            ) as delete_document,
        ):
            response = await client.post(
                "/graphql",
                json={
                    "query": """
                        mutation Reject($id: String!) {
                            rejectCvReview(reviewId: $id, note: "Unsupported information")
                        }
                    """,
                    "variables": {"id": review_id},
                },
            )
            delete_document.assert_awaited_once_with(document_id)
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = previous_semantic_flag
    assert response.json()["data"]["rejectCvReview"] is True

    async with factory() as session:
        crew = (
            await session.execute(select(CrewMember).where(CrewMember.id == crew_id))
        ).scalar_one()
        document = (
            await session.execute(select(Document).where(Document.id == document_id))
        ).scalar_one()
    assert crew.publication_status == "approved"
    assert document.extraction_status == "rejected"


@pytest.mark.asyncio
async def test_rejecting_an_already_rejected_cv_retries_vector_cleanup(db_session):
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(id=crew_id, full_name="Already Rejected CV", publication_status="approved")
    )
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew_id,
            file_name="rejected-cv.pdf",
            file_type="pdf",
            file_size=100,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="cv",
            extraction_status="rejected",
        )
    )
    await db_session.flush()
    db_session.add(
        CVReview(
            id=review_id,
            document_id=document_id,
            crew_member_id=crew_id,
            status="rejected",
            submitted_by="staff-1",
        )
    )
    await db_session.commit()

    settings = get_settings()
    previous_semantic_flag = settings.ENABLE_SEMANTIC_SEARCH
    settings.ENABLE_SEMANTIC_SEARCH = True
    try:
        with (
            patch(
                "app.services.cv_review.consultant_knowledge_service.index_crew_member",
                new=AsyncMock(),
            ) as index_crew,
            patch(
                "app.services.qdrant.qdrant_service.delete_document", new=AsyncMock()
            ) as delete_document,
            patch(
                "app.services.cv_review.consultant_knowledge_service.reconcile_document_index",
                new=AsyncMock(),
            ) as reconcile_document,
            patch("app.services.cv_review.cache_service.delete", new=AsyncMock()) as delete_cache,
        ):
            result = await cv_review_service.reject(
                review_id, reviewer_id="admin-1", note="Retry cleanup"
            )
            index_crew.assert_awaited_once()
            delete_document.assert_awaited_once_with(document_id)
            reconcile_document.assert_awaited_once_with(document_id)
            assert delete_cache.await_count == 2
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = previous_semantic_flag

    assert result.status == "rejected"


@pytest.mark.asyncio
async def test_approving_an_already_approved_cv_repairs_derived_projections(db_session):
    crew_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(id=crew_id, full_name="Already Approved CV", publication_status="approved")
    )
    db_session.add(
        Document(
            id=document_id,
            crew_member_id=crew_id,
            file_name="approved-cv.pdf",
            file_type="pdf",
            file_size=100,
            storage_type="local",
            storage_path=f"/tmp/{document_id}.pdf",
            classification="cv",
            extraction_status="approved",
        )
    )
    await db_session.flush()
    db_session.add(
        CVReview(
            id=review_id,
            document_id=document_id,
            crew_member_id=crew_id,
            status="approved",
            submitted_by="staff-1",
        )
    )
    await db_session.commit()

    settings = get_settings()
    previous_semantic_flag = settings.ENABLE_SEMANTIC_SEARCH
    settings.ENABLE_SEMANTIC_SEARCH = True
    try:
        with (
            patch(
                "app.services.cv_review.consultant_knowledge_service.index_crew_member",
                new=AsyncMock(),
            ) as index_crew,
            patch(
                "app.tasks.document_tasks.index_document_embeddings.delay",
                new=MagicMock(),
            ) as queue_embedding,
            patch(
                "app.services.cv_review.consultant_knowledge_service.reconcile_document_index",
                new=AsyncMock(),
            ) as reconcile_document,
        ):
            result = await cv_review_service.approve(
                review_id,
                approved_data={"full_name": "Already Approved CV"},
                reviewer_id="admin-1",
            )
            index_crew.assert_awaited_once()
            queue_embedding.assert_called_once_with(document_id)
            reconcile_document.assert_awaited_once_with(document_id)
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = previous_semantic_flag

    assert result.status == "approved"


@pytest.mark.asyncio
async def test_approving_an_already_approved_cv_requeues_all_published_documents(db_session):
    """Approval retries repair older approved documents too, not only the CV."""
    crew_id = str(uuid.uuid4())
    current_document_id = str(uuid.uuid4())
    older_document_id = str(uuid.uuid4())
    review_id = str(uuid.uuid4())
    db_session.add(
        CrewMember(
            id=crew_id, full_name="Published Retry Contractor", publication_status="approved"
        )
    )
    db_session.add_all(
        [
            Document(
                id=current_document_id,
                crew_member_id=crew_id,
                file_name="current.pdf",
                file_type="pdf",
                file_size=10,
                storage_type="local",
                storage_path=f"/tmp/{current_document_id}.pdf",
                extraction_status="approved",
            ),
            Document(
                id=older_document_id,
                crew_member_id=crew_id,
                file_name="older.pdf",
                file_type="pdf",
                file_size=10,
                storage_type="local",
                storage_path=f"/tmp/{older_document_id}.pdf",
                extraction_status="extracted",
            ),
        ]
    )
    await db_session.flush()
    db_session.add(
        CVReview(
            id=review_id,
            document_id=current_document_id,
            crew_member_id=crew_id,
            status="approved",
            submitted_by="staff-1",
        )
    )
    await db_session.commit()

    settings = get_settings()
    previous_semantic_flag = settings.ENABLE_SEMANTIC_SEARCH
    settings.ENABLE_SEMANTIC_SEARCH = True
    try:
        with (
            patch(
                "app.services.cv_review.consultant_knowledge_service.index_crew_member",
                new=AsyncMock(),
            ),
            patch(
                "app.tasks.document_tasks.index_document_embeddings.delay",
                new=MagicMock(),
            ) as queue_embedding,
            patch(
                "app.services.cv_review.consultant_knowledge_service.reconcile_document_index",
                new=AsyncMock(),
            ) as reconcile_document,
        ):
            await cv_review_service.approve(
                review_id,
                approved_data={},
                reviewer_id="admin-1",
            )
            assert {call.args[0] for call in queue_embedding.call_args_list} == {
                current_document_id,
                older_document_id,
            }
            assert {call.args[0] for call in reconcile_document.await_args_list} == {
                current_document_id,
                older_document_id,
            }
    finally:
        settings.ENABLE_SEMANTIC_SEARCH = previous_semantic_flag
