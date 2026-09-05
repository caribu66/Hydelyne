"""Security and publication regressions for reviewed CV ingestion."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.database import get_session_factory
from app.models import CrewMember, CVReview, Document
from app.services.crew import crew_service
from app.services.cv_review import cv_review_service


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
        json={"query": "query { cvReviews(limit: 10, offset: 0) { id } }"},
    )

    assert response.json()["data"]["cvReviews"] == [{"id": review_ids[0]}]


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

    with (
        patch(
            "app.services.cv_review.consultant_knowledge_service.index_crew_member",
            new=AsyncMock(),
        ),
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
