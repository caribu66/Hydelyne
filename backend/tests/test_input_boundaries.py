"""Regression tests for GraphQL mutation DTO persistence limits."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.services.crew import certification_service


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "x" * 256),
        ("phone", "x" * 51),
        ("nationality", "x" * 101),
        ("country_of_residence", "x" * 101),
        ("gender", "x" * 51),
        ("flying_point", "x" * 256),
    ],
)
def test_crew_create_dto_rejects_database_overflow_values(field, value):
    from app.graphql.dtos import CrewMemberCreateDTO

    with pytest.raises(ValidationError):
        CrewMemberCreateDTO(full_name="Test Crew", **{field: value})


def test_graphql_model_projection_restores_defaults_for_legacy_null_statuses():
    from app.graphql.schema import (
        _model_to_graphql_certification,
        _model_to_graphql_crew_member,
        _model_to_graphql_document,
        _model_to_graphql_project,
    )
    from app.models import Certification, CrewMember, Document, Project

    crew = CrewMember(id="crew-1", full_name="Legacy Crew")
    crew.publication_status = None
    crew.availability_status = None
    certification = Certification(id="cert-1", crew_member_id=crew.id, cert_type="BOSIET")
    certification.status = None
    certification.verification_status = None
    document = Document(
        id="doc-1",
        file_name="legacy.pdf",
        file_type="application/pdf",
        file_size=1,
        storage_type="local",
        storage_path="/tmp/legacy.pdf",
    )
    document.extraction_status = None
    project = Project(
        id="project-1",
        client_name="Client",
        project_name="Legacy Project",
        project_type="survey",
    )
    project.status = None

    crew_projection = _model_to_graphql_crew_member(crew)
    assert crew_projection.publication_status == "draft"
    assert crew_projection.availability_status == "unavailable"
    assert _model_to_graphql_certification(certification).status == "pending_verification"
    assert _model_to_graphql_certification(certification).verification_status == "unverified"
    assert _model_to_graphql_document(document).extraction_status == "pending"
    assert _model_to_graphql_project(project).status == "planning"


def test_crew_create_dto_bounds_language_values_and_count():
    from app.graphql.dtos import CrewMemberCreateDTO

    with pytest.raises(ValidationError):
        CrewMemberCreateDTO(full_name="Test Crew", languages=["x" * 256])
    with pytest.raises(ValidationError):
        CrewMemberCreateDTO(full_name="Test Crew", languages=["English"] * 101)


def test_certification_create_dto_rejects_database_overflow_values():
    from app.graphql.dtos import CertificationCreateDTO

    with pytest.raises(ValidationError):
        CertificationCreateDTO(
            crew_member_id="crew-1",
            cert_type="BOSIET",
            cert_number="x" * 101,
        )


def test_upload_validation_rejects_database_overflow_filename():
    import io

    from fastapi import UploadFile

    from app.services.upload import document_upload_service

    valid, message = document_upload_service.validate_file(
        UploadFile(filename="x" * 256 + ".pdf", file=io.BytesIO()),
    )

    assert valid is False
    assert "255" in message


def test_storage_filename_bounds_storage_key_and_preserves_extension():
    from app.services.upload import MAX_STORAGE_FILENAME_LENGTH, storage_filename

    stored = storage_filename("x" * 240 + ".pdf")

    assert len(stored) == MAX_STORAGE_FILENAME_LENGTH
    assert stored.endswith(".pdf")


def test_graphql_json_input_rejects_oversized_payload():
    from graphql import GraphQLError

    from app.graphql.schema import MAX_GRAPHQL_JSON_INPUT_LENGTH, _parse_json_object

    with pytest.raises(GraphQLError) as error:
        _parse_json_object(
            '{"value":"' + "x" * MAX_GRAPHQL_JSON_INPUT_LENGTH + '"}',
            field="approved_data",
        )

    assert error.value.extensions["code"] == "BAD_USER_INPUT"


def test_graphql_review_note_rejects_oversized_payload():
    from graphql import GraphQLError

    from app.graphql.schema import MAX_REVIEW_NOTE_LENGTH, _validate_review_note

    with pytest.raises(GraphQLError) as error:
        _validate_review_note("x" * (MAX_REVIEW_NOTE_LENGTH + 1))

    assert error.value.extensions["code"] == "BAD_USER_INPUT"


@pytest.mark.asyncio
async def test_shared_review_note_limit_matches_service_boundaries():
    from app.domain.input_limits import MAX_REVIEW_NOTE_LENGTH
    from app.services.cv_review import CVReviewService
    from app.services.document_requests import DocumentRequestService

    assert MAX_REVIEW_NOTE_LENGTH == 2_000
    with pytest.raises(ValueError):
        await DocumentRequestService().resolve_review(
            actor_id="actor-1",
            action="approve",
            note="x" * (MAX_REVIEW_NOTE_LENGTH + 1),
        )
    with pytest.raises(ValueError):
        await CVReviewService().reject(
            "review-1",
            reviewer_id="actor-1",
            note="x" * (MAX_REVIEW_NOTE_LENGTH + 1),
        )
    with pytest.raises(ValueError, match="Review note must be a string"):
        await DocumentRequestService().resolve_review(
            actor_id="actor-1",
            action="approve",
            note=42,
        )
    with pytest.raises(ValueError, match="Review note must be a string"):
        await CVReviewService().reject("review-1", reviewer_id="actor-1", note=42)


@pytest.mark.asyncio
async def test_crew_update_rejects_protected_fields_before_database_access():
    from app.services.crew import crew_service

    with pytest.raises(ValueError, match="Unsupported crew member update fields"):
        await crew_service.update_crew_member("crew-1", {"role": "admin"})


@pytest.mark.asyncio
async def test_project_update_rejects_unknown_status_before_database_access():
    from app.services.project import project_service

    with pytest.raises(ValueError, match="Invalid project status"):
        await project_service.update_project("project-1", "archived")
    with pytest.raises(ValueError, match="Invalid project status"):
        await project_service.update_project("project-1", ["active"])


def test_extracted_certification_status_preserves_verified_lifecycle():
    from datetime import date, timedelta

    from app.services.crew import _extracted_certification_status

    assert _extracted_certification_status(date.today() + timedelta(days=90), "verified") == "valid"
    assert (
        _extracted_certification_status(date.today() + timedelta(days=10), "verified")
        == "expiring_soon"
    )
    assert _extracted_certification_status(date.today(), "unverified") == "pending_verification"


@pytest.mark.asyncio
async def test_certification_service_rejects_oversized_text_before_database_access():
    from app.services.crew import certification_service

    with pytest.raises(ValueError, match="cert_type"):
        await certification_service.add_certification("crew-1", "x" * 51)
    with pytest.raises(ValueError, match="cert_number"):
        await certification_service.add_certification("crew-1", "BOSIET", cert_number="x" * 101)
    with pytest.raises(ValueError, match="issuing_body must be a string"):
        await certification_service.add_certification("crew-1", "BOSIET", issuing_body=42)
    with pytest.raises(ValueError, match="Invalid certification status"):
        await certification_service.update_certification("cert-1", ["valid"])
    with pytest.raises(ValueError, match="Invalid certification verification status"):
        await certification_service.verify_certification("cert-1", ["verified"])


@pytest.mark.asyncio
async def test_staff_role_service_rejects_truthy_non_boolean_before_database_access():
    from app.services.crew import _validate_boolean_flag

    with pytest.raises(ValueError, match="enabled must be a boolean"):
        _validate_boolean_flag("false", "enabled")


def test_crew_creation_rejects_truthy_workflow_flags_before_database_access():
    from app.services.crew import _validate_boolean_flag

    with pytest.raises(ValueError, match="allow_duplicate must be a boolean"):
        _validate_boolean_flag("false", "allow_duplicate")


def test_availability_status_rejects_unknown_values_before_database_access():
    from app.services.crew import _validate_availability_status

    with pytest.raises(ValueError, match="Invalid availability status"):
        _validate_availability_status("deployed")


def test_availability_update_requires_date_for_active_assignment():
    from app.services.crew import _availability_date_for_update

    with pytest.raises(ValueError, match="available_date is required"):
        _availability_date_for_update("on_assignment", None)
    assert _availability_date_for_update("available", None) is None


def test_crew_update_rejects_bounded_column_overflow_before_database_access():
    from app.services.crew import _validate_crew_update_values

    with pytest.raises(ValueError, match="email must be 255"):
        _validate_crew_update_values({"email": "x" * 256})
    with pytest.raises(ValueError, match="full_name must not be empty"):
        _validate_crew_update_values({"full_name": "   "})


def test_crew_update_rejects_unbounded_profile_lists_before_database_access():
    from app.services.crew import _validate_crew_update_values

    with pytest.raises(ValueError, match="languages must contain at most"):
        _validate_crew_update_values({"languages": ["English"] * 101})
    with pytest.raises(ValueError, match="tags values must be"):
        _validate_crew_update_values({"tags": ["x" * 256]})


def test_crew_creation_uses_profile_list_bounds():
    from app.services.crew import _validate_crew_update_values

    with pytest.raises(ValueError, match="tags must contain at most"):
        _validate_crew_update_values({"tags": ["tag"] * 101})


def test_project_creation_rejects_invalid_raw_model_values():
    from app.models import Project
    from app.services.project import _validate_project_values

    with pytest.raises(ValueError, match="client_name must not be empty"):
        _validate_project_values(
            Project(client_name="   ", project_name="Project", project_type="other")
        )
    with pytest.raises(ValueError, match="location must be 255"):
        _validate_project_values(
            Project(
                client_name="Client",
                project_name="Project",
                project_type="other",
                location="x" * 256,
            )
        )


def test_project_creation_rejects_reversed_dates():
    from datetime import date

    from app.models import Project
    from app.services.project import _validate_project_values

    with pytest.raises(ValueError, match="start_date must be on or before end_date"):
        _validate_project_values(
            Project(
                client_name="Client",
                project_name="Project",
                project_type="other",
                start_date=date(2026, 9, 12),
                end_date=date(2026, 9, 11),
            )
        )


def test_certification_creation_rejects_reversed_dates_before_database_access():
    from datetime import date, datetime

    from app.services.crew import certification_service

    with pytest.raises(ValueError, match="issue_date must be on or before expiry_date"):
        certification_service._validate_certification_dates(
            date(2026, 9, 12), date(2026, 9, 11)
        )
    with pytest.raises(ValueError, match="expiry_date must be a date"):
        certification_service._validate_certification_dates(date.today(), "2026-09-12")
    with pytest.raises(ValueError, match="expiry_date must be a date"):
        certification_service._validate_certification_dates(date.today(), datetime.now())


@pytest.mark.asyncio
async def test_expiring_certification_listing_rejects_malformed_bounds_before_database_access():
    from app.services.crew import certification_service

    with pytest.raises(ValueError, match="days must be an integer"):
        await certification_service.get_expiring_certifications(days="30")
    with pytest.raises(ValueError, match="limit must be an integer"):
        await certification_service.get_expiring_certifications(limit="100")


def test_project_assignment_rejects_malformed_crew_ids_before_database_access():
    from app.services.project import _validate_crew_ids

    with pytest.raises(ValueError, match="non-empty strings"):
        _validate_crew_ids(["crew-1", ""])
    with pytest.raises(ValueError, match="36 characters"):
        _validate_crew_ids(["x" * 37])


@pytest.mark.asyncio
async def test_assignment_creation_rejects_malformed_status_and_rate_before_database_access():
    from datetime import date

    from app.services.assignment import assignment_service

    with pytest.raises(ValueError, match="Invalid assignment status"):
        await assignment_service.create_assignment(
            crew_member_id="crew-1",
            vessel_imo="1234567",
            role_on_board="Surveyor",
            start_date=date.today(),
            end_date=date.today(),
            status=["proposed"],
        )
    with pytest.raises(ValueError, match="finite non-negative"):
        await assignment_service.create_assignment(
            crew_member_id="crew-1",
            vessel_imo="1234567",
            role_on_board="Surveyor",
            start_date=date.today(),
            end_date=date.today(),
            agreed_day_rate="100",
        )
    with pytest.raises(ValueError, match="vessel_imo must be a string"):
        await assignment_service.create_assignment(
            crew_member_id="crew-1",
            vessel_imo=1234567,
            role_on_board="Surveyor",
            start_date=date.today(),
            end_date=date.today(),
        )


@pytest.mark.asyncio
async def test_assignment_listing_rejects_non_string_vessel_filter_before_database_access():
    from app.services.assignment import assignment_service

    with pytest.raises(ValueError, match="vessel_imo must be a string"):
        await assignment_service.list_assignments(vessel_imo=1234567)


@pytest.mark.asyncio
async def test_crew_listing_rejects_non_string_search_before_database_access():
    from app.services.crew import crew_service

    with pytest.raises(ValueError, match="Search query must be a string"):
        await crew_service.list_crew_members(search=123)


def test_crew_creation_rejects_privileged_roles_before_database_access():
    from app.services.crew import _validate_new_crew_role

    with pytest.raises(ValueError, match="cannot be created with privileged roles"):
        _validate_new_crew_role("admin")
    _validate_new_crew_role(None)
    _validate_new_crew_role("user")


def test_pagination_rejects_non_integer_values_before_query_construction():
    from app.domain.input_limits import validate_pagination

    with pytest.raises(ValueError, match="limit must be an integer"):
        validate_pagination("50", 0)
    with pytest.raises(ValueError, match="offset must be an integer"):
        validate_pagination(50, False)
    assert validate_pagination(-10, -2) == (1, 0)


@pytest.mark.parametrize("query", ["   ", "x" * 501])
def test_graphql_search_validator_rejects_invalid_queries(query):
    from graphql import GraphQLError

    from app.graphql.schema import _validate_graphql_search_query

    with pytest.raises(GraphQLError) as error:
        _validate_graphql_search_query(query)

    assert error.value.extensions["code"] == "BAD_USER_INPUT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resolver_name", "kwargs"),
    [
        ("campaign_assignments", {"vessel_imo": " "}),
        ("vessel_roster", {"imo": "9683934/position"}),
    ],
)
async def test_assignment_graphql_maps_vessel_validation_to_bad_user_input(
    monkeypatch, resolver_name, kwargs
):
    from graphql import GraphQLError

    from app.graphql.schema import Query
    from app.services.assignment import assignment_service

    monkeypatch.setattr(
        assignment_service,
        "list_assignments",
        AsyncMock(side_effect=ValueError("vessel_imo is invalid")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="staff-1", role="staff")}
    )
    resolver = getattr(Query, resolver_name).__wrapped__

    with pytest.raises(GraphQLError) as error:
        await resolver(Query(), info, **kwargs)

    assert error.value.extensions["code"] == "BAD_USER_INPUT"


@pytest.mark.asyncio
async def test_compliance_status_graphql_maps_missing_profile_to_not_found(monkeypatch):
    from graphql import GraphQLError

    from app.graphql.schema import Query
    from app.services.crew import crew_service

    monkeypatch.setattr(crew_service, "can_access_profile", AsyncMock(return_value=False))
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )

    with pytest.raises(GraphQLError) as error:
        await Query.compliance_status.__wrapped__(
            Query(), info, crew_id="missing-crew"
        )

    assert error.value.extensions["code"] == "NOT_FOUND"


@pytest.mark.asyncio
@pytest.mark.parametrize("resolver_name", ["confirm_extraction", "confirm_document_match"])
async def test_document_graphql_maps_missing_document_to_not_found(monkeypatch, resolver_name):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.document_service import document_service

    method_name = (
        "confirm_extraction" if resolver_name == "confirm_extraction" else "link_to_crew_member"
    )
    monkeypatch.setattr(document_service, method_name, AsyncMock(return_value=None))
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )
    resolver = getattr(Mutation, resolver_name).__wrapped__
    kwargs = (
        {"document_id": "missing-document", "data": "{}"}
        if resolver_name == "confirm_extraction"
        else {"document_id": "missing-document", "crew_id": "crew-1"}
    )

    with pytest.raises(GraphQLError) as error:
        await resolver(Mutation(), info, **kwargs)

    assert error.value.extensions["code"] == "NOT_FOUND"


@pytest.mark.asyncio
@pytest.mark.parametrize("resolver_name", ["update_certification", "verify_certification"])
async def test_certification_graphql_maps_missing_id_to_not_found(monkeypatch, resolver_name):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.crew import certification_service

    method_name = (
        "update_certification" if resolver_name == "update_certification" else "verify_certification"
    )
    monkeypatch.setattr(
        certification_service,
        method_name,
        AsyncMock(side_effect=ValueError("Certification missing-id not found")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )
    resolver = getattr(Mutation, resolver_name).__wrapped__
    kwargs = (
        {"id": "missing-cert"}
        if resolver_name == "update_certification"
        else {"id": "missing-cert", "status": SimpleNamespace(value="verified")}
    )

    with pytest.raises(GraphQLError) as error:
        await resolver(Mutation(), info, **kwargs)

    assert error.value.extensions["code"] == "NOT_FOUND"
    assert "missing-cert" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("resolver_name", ["update_project", "assign_crew_to_project"])
async def test_project_graphql_maps_missing_resource_to_not_found(monkeypatch, resolver_name):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.project import project_service

    method_name = "update_project" if resolver_name == "update_project" else "assign_crew"
    monkeypatch.setattr(
        project_service,
        method_name,
        AsyncMock(side_effect=ValueError("Project missing-id not found")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )
    resolver = getattr(Mutation, resolver_name).__wrapped__
    kwargs = (
        {"id": "missing-project"}
        if resolver_name == "update_project"
        else {"project_id": "missing-project", "crew_ids": []}
    )

    with pytest.raises(GraphQLError) as error:
        await resolver(Mutation(), info, **kwargs)

    assert error.value.extensions["code"] == "NOT_FOUND"
    assert "missing-project" not in str(error.value)


@pytest.mark.asyncio
async def test_create_project_graphql_maps_dto_validation_to_bad_user_input():
    from graphql import GraphQLError

    from app.graphql.schema import Mutation

    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )

    with pytest.raises(GraphQLError) as error:
        await Mutation.create_project.__wrapped__(
            Mutation(),
            info,
            client_name="",
            project_name="Valid project",
            project_type=SimpleNamespace(value="marine_seismic"),
        )

    assert error.value.extensions["code"] == "BAD_USER_INPUT"


@pytest.mark.asyncio
async def test_reprocess_document_graphql_maps_missing_document_to_not_found(monkeypatch):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.document_service import document_service

    monkeypatch.setattr(
        document_service,
        "reprocess_document",
        AsyncMock(side_effect=ValueError("Document secret-id not found")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )

    with pytest.raises(GraphQLError) as error:
        await Mutation.reprocess_document.__wrapped__(
            Mutation(), info, document_id="secret-id"
        )

    assert error.value.extensions["code"] == "NOT_FOUND"
    assert "secret-id" not in str(error.value)


@pytest.mark.asyncio
async def test_add_certification_graphql_maps_missing_crew_to_not_found(monkeypatch):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.crew import certification_service

    monkeypatch.setattr(
        certification_service,
        "add_certification",
        AsyncMock(side_effect=ValueError("Crew member not found")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )

    with pytest.raises(GraphQLError) as error:
        await Mutation.add_certification.__wrapped__(
            Mutation(),
            info,
            crew_id="missing-crew",
            cert_type=SimpleNamespace(value="BOSIET"),
        )

    assert error.value.extensions["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_create_crew_graphql_maps_dto_validation_to_bad_user_input():
    from graphql import GraphQLError

    from app.graphql.schema import Mutation

    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )

    with pytest.raises(GraphQLError) as error:
        await Mutation.create_crew_member.__wrapped__(
            Mutation(), info, full_name="", cv_submission=False, confirm_distinct=False
        )

    assert error.value.extensions["code"] == "BAD_USER_INPUT"


@pytest.mark.asyncio
async def test_update_crew_graphql_maps_missing_id_to_not_found(monkeypatch):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.crew import crew_service

    monkeypatch.setattr(
        crew_service,
        "update_crew_member",
        AsyncMock(side_effect=ValueError("Crew member secret-id not found")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )

    with pytest.raises(GraphQLError) as error:
        await Mutation.update_crew_member.__wrapped__(
            Mutation(), info, id="secret-id"
        )

    assert error.value.extensions["code"] == "NOT_FOUND"
    assert "secret-id" not in str(error.value)


@pytest.mark.asyncio
async def test_delete_crew_graphql_maps_self_delete_to_forbidden(monkeypatch):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.crew import crew_service

    monkeypatch.setattr(
        crew_service,
        "delete_crew_member",
        AsyncMock(side_effect=ValueError("You cannot delete your own administrator account")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )

    with pytest.raises(GraphQLError) as error:
        await Mutation.delete_crew_member.__wrapped__(
            Mutation(), info, id="admin-1"
        )

    assert error.value.extensions["code"] == "FORBIDDEN"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("User not found", "NOT_FOUND"),
        ("Administrator roles cannot be changed here", "FORBIDDEN"),
    ],
)
async def test_set_staff_role_graphql_maps_service_errors(monkeypatch, message, code):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.crew import crew_service

    monkeypatch.setattr(
        crew_service,
        "set_staff_role",
        AsyncMock(side_effect=ValueError(message)),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )

    with pytest.raises(GraphQLError) as error:
        await Mutation.set_staff_role.__wrapped__(
            Mutation(), info, user_id="target-user", enabled=True
        )

    assert error.value.extensions["code"] == code


@pytest.mark.asyncio
@pytest.mark.parametrize("resolver_name", ["approve_cv_review", "reject_cv_review"])
async def test_cv_review_graphql_maps_missing_review_to_not_found(monkeypatch, resolver_name):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.cv_review import cv_review_service

    method_name = "approve" if resolver_name == "approve_cv_review" else "reject"
    monkeypatch.setattr(
        cv_review_service,
        method_name,
        AsyncMock(side_effect=ValueError("CV review secret-id not found")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )
    resolver = getattr(Mutation, resolver_name).__wrapped__
    kwargs = (
        {"review_id": "secret-id", "approved_data": "{}", "note": None}
        if resolver_name == "approve_cv_review"
        else {"review_id": "secret-id", "note": "Not suitable"}
    )

    with pytest.raises(GraphQLError) as error:
        await resolver(Mutation(), info, **kwargs)

    assert error.value.extensions["code"] == "NOT_FOUND"
    assert "secret-id" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resolver_name", "method_name", "message"),
    [
        (
            "confirm_extraction",
            "confirm_extraction",
            "Document extraction is currently in progress",
        ),
        ("confirm_document_match", "link_to_crew_member", "Crew member not found"),
    ],
)
async def test_document_graphql_maps_service_conflicts_and_missing_links(
    monkeypatch, resolver_name, method_name, message
):
    from graphql import GraphQLError

    from app.graphql.schema import Mutation
    from app.services.document_service import document_service

    monkeypatch.setattr(
        document_service,
        method_name,
        AsyncMock(side_effect=ValueError(message)),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )
    resolver = getattr(Mutation, resolver_name).__wrapped__
    kwargs = (
        {"document_id": "document-1", "data": "{}"}
        if resolver_name == "confirm_extraction"
        else {"document_id": "document-1", "crew_id": "crew-1"}
    )

    with pytest.raises(GraphQLError) as error:
        await resolver(Mutation(), info, **kwargs)

    expected_code = "CONFLICT" if resolver_name == "confirm_extraction" else "NOT_FOUND"
    assert error.value.extensions["code"] == expected_code


@pytest.mark.asyncio
async def test_vessel_record_graphql_maps_invalid_imo_to_bad_user_input(monkeypatch):
    from graphql import GraphQLError

    from app.graphql.schema import Query
    from app.services.assignment import assignment_service

    monkeypatch.setattr(
        assignment_service,
        "get_vessel",
        AsyncMock(side_effect=ValueError("vessel_imo contains invalid characters")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="staff-1", role="staff")}
    )

    with pytest.raises(GraphQLError) as error:
        await Query.vessel_record.__wrapped__(
            Query(), info, imo="9683934/secret"
        )

    assert error.value.extensions["code"] == "BAD_USER_INPUT"


@pytest.mark.asyncio
async def test_evaluate_compliance_graphql_maps_missing_crew_to_not_found(monkeypatch):
    from graphql import GraphQLError

    from app.graphql.schema import Query
    from app.services.assignment import assignment_service

    monkeypatch.setattr(
        assignment_service,
        "evaluate_compliance",
        AsyncMock(side_effect=ValueError("Crew member secret-id not found")),
    )
    info = SimpleNamespace(
        context={"current_user": SimpleNamespace(id="admin-1", role="admin")}
    )

    with pytest.raises(GraphQLError) as error:
        await Query.evaluate_assignment_compliance.__wrapped__(
            Query(),
            info,
            crew_member_id="secret-id",
            start_date="2026-10-01",
            end_date="2026-10-02",
        )

    assert error.value.extensions["code"] == "NOT_FOUND"
    assert "secret-id" not in str(error.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("file_name", "x" * 256),
        ("file_type", "x" * 51),
        ("file_size", 0),
        ("storage_path", "x" * 501),
    ],
)
def test_document_service_metadata_rejects_invalid_values(field, value):
    from app.services.document_service import _validate_document_metadata

    values = {
        "file_name": "document.pdf",
        "file_type": "pdf",
        "file_size": 10,
        "storage_path": "/tmp/document.pdf",
        "uploaded_by": None,
    }
    values[field] = value
    with pytest.raises(ValueError):
        _validate_document_metadata(**values)


def test_document_service_metadata_rejects_unmanaged_dropbox_path():
    from app.services.document_service import _validate_document_metadata

    with pytest.raises(ValueError, match="managed Dropbox path"):
        _validate_document_metadata(
            "document.pdf", "pdf", 10, "/hydenlyne/../outside.pdf", None
        )


def test_document_audit_history_keeps_only_recent_entries():
    from app.services.audit import MAX_DOCUMENT_AUDIT_ENTRIES, append_document_audit_entry

    history: object = [{"sequence": index} for index in range(MAX_DOCUMENT_AUDIT_ENTRIES)]
    bounded = append_document_audit_entry(history, {"sequence": MAX_DOCUMENT_AUDIT_ENTRIES})

    assert len(bounded) == MAX_DOCUMENT_AUDIT_ENTRIES
    assert bounded[0]["sequence"] == 1
    assert bounded[-1]["sequence"] == MAX_DOCUMENT_AUDIT_ENTRIES


def test_certificate_date_parser_normalizes_datetime_to_date():
    parsed = certification_service._parse_date(datetime(2026, 9, 12, 14, 30))

    assert parsed == date(2026, 9, 12)


@pytest.mark.asyncio
async def test_document_confirmation_rejects_non_object_data_before_database_access():
    from app.services.document_service import document_service

    with pytest.raises(ValueError, match="JSON object"):
        await document_service.confirm_extraction("document-1", [])


@pytest.mark.asyncio
async def test_crew_update_rejects_non_object_updates_before_database_access():
    from app.services.crew import crew_service

    with pytest.raises(ValueError, match="object"):
        await crew_service.update_crew_member("crew-1", [])


@pytest.mark.asyncio
async def test_report_builder_rejects_non_object_filters_before_database_access():
    from app.services.reports import report_service

    with pytest.raises(ValueError, match="object"):
        await report_service.build_report_data("availability", None, filters=[])


@pytest.mark.asyncio
async def test_report_builder_rejects_unknown_type_before_database_access():
    from app.services.reports import report_service

    with pytest.raises(ValueError, match="Unknown report type"):
        await report_service.build_report_data("unknown", None)


@pytest.mark.asyncio
async def test_certificate_projection_rejects_non_object_data_before_database_access():
    with pytest.raises(ValueError, match="JSON object"):
        await certification_service.link_extracted_certificate("crew-1", "document-1", [])


@pytest.mark.asyncio
async def test_cv_processing_rejects_non_object_data_before_database_access():
    from app.services.cv_processing import cv_processing_service

    with pytest.raises(ValueError, match="JSON object"):
        await cv_processing_service.process_cv_extraction("crew-1", [])


def test_classification_normalization_handles_non_string_values():
    from app.domain.fields import normalize_classification

    assert normalize_classification(123) == "other"


def test_report_availability_filter_rejects_unknown_status_but_allows_null_default():
    from app.services.reports import validate_report_filters

    validate_report_filters("availability", {"availability_status": None})
    with pytest.raises(ValueError, match="Invalid availability_status"):
        validate_report_filters("availability", {"availability_status": "unknown"})


@pytest.mark.asyncio
async def test_contractor_upload_rechecks_expiry_before_persisting():
    from fastapi import HTTPException

    from app.api.documents import upload_requested_document

    class _Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    expired_request = SimpleNamespace(
        id="request-1",
        status="active",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    class _Session:
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def execute(self, _statement):
            self.calls += 1
            return _Result(expired_request)

        async def commit(self):
            return None

    with (
        patch(
            "app.api.documents.document_request_service.get_active_request",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    id="request-1",
                    crew_member_id="crew-1",
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
                )
            ),
        ),
        patch("app.api.documents.document_upload_service.validate_file", return_value=(True, "")),
        patch(
            "app.api.documents.document_upload_service.save_file",
            new=AsyncMock(return_value=("document-1", "/tmp/document.pdf", 10)),
        ) as save_file,
        patch("app.api.documents.document_upload_service.get_file_type", return_value="pdf"),
        patch("app.api.documents.get_session_factory", return_value=lambda: _Session()),
        patch("app.api.documents._cleanup_saved_upload", new=AsyncMock()) as cleanup,
    ):
        with pytest.raises(HTTPException) as error:
            await upload_requested_document(
                "token",
                SimpleNamespace(filename="document.pdf"),
                None,
                "retry-key",
            )

    assert error.value.status_code == 404
    save_file.assert_not_awaited()
    cleanup.assert_not_awaited()


@pytest.mark.asyncio
async def test_contractor_upload_rechecks_publication_before_persisting():
    from fastapi import HTTPException

    from app.api.documents import upload_requested_document

    request_row = SimpleNamespace(
        id="request-1",
        status="active",
        crew_member_id="crew-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    rejected_crew = SimpleNamespace(id="crew-1", publication_status="rejected")

    class _Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class _Session:
        values = [request_row, rejected_crew]
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def execute(self, _statement):
            value = self.values[self.calls]
            self.calls += 1
            return _Result(value)

    with (
        patch(
            "app.api.documents.document_request_service.get_active_request",
            new=AsyncMock(return_value=request_row),
        ),
        patch("app.api.documents.document_upload_service.validate_file", return_value=(True, "")),
        patch(
            "app.api.documents.document_upload_service.save_file",
            new=AsyncMock(return_value=("document-1", "/tmp/document.pdf", 10)),
        ) as save_file,
        patch("app.api.documents.get_session_factory", return_value=lambda: _Session()),
        patch("app.api.documents._cleanup_saved_upload", new=AsyncMock()) as cleanup,
    ):
        with pytest.raises(HTTPException) as error:
            await upload_requested_document(
                "token",
                SimpleNamespace(filename="document.pdf"),
                None,
                "retry-key",
            )

    assert error.value.status_code == 404
    save_file.assert_not_awaited()
    cleanup.assert_not_awaited()
