from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import strawberry
from strawberry import Info

from app.auth.decorators import require_admin, require_auth, require_staff
from app.database import get_session_factory
from app.domain.access_tiers import tier_for_role
from app.graphql.dtos import (
    CertificationCreateDTO,
    CrewMemberCreateDTO,
    CrewMemberUpdateDTO,
    DocumentCreateDTO,
    ProjectCreateDTO,
)
from app.graphql.mappers import (
    dto_to_crew_member_model,
    dto_to_project_model,
)
from app.graphql.scrub import scrub_crew_member, scrub_document, scrub_project
from app.graphql.types import (
    AssignmentComplianceReportType,
    AuthPayload,
    AvailabilityStatus,
    CampaignAssignmentStatus,
    CampaignAssignmentType,
    Certification,
    CertStatus,
    CertType,
    ComplianceCheckItemType,
    CreateCampaignAssignmentInput,
    CrewMember,
    CrewQueryResponse,
    CVExtractionResult,
    CVReviewType,
    DocumentClassification,
    DocumentType,
    InsuranceInfo,
    MedicalInfo,
    PassportInfo,
    Project,
    ProjectStatus,
    ProjectType,
    Report,
    ReportType,
    VerificationStatus,
    VesselIdType,
    VesselPosition,
    VesselSearchResponse,
    VesselSummary,
    VesselType,
    VisaInfo,
    WorkHistory,
)
from app.models import CampaignAssignment as CampaignAssignmentModel
from app.models import Certification as CertificationModel
from app.models import CrewMember as CrewMemberModel
from app.models import Document as DocumentModel
from app.models import Project as ProjectModel
from app.models import Vessel as VesselModel
from app.models import WorkHistory as WorkHistoryModel
from app.services.audit import audit_service
from app.services.crew import (
    PossibleDuplicateError,
    auth_service,
    certification_service,
    crew_service,
)
from app.services.cv_review import cv_review_service
from app.services.document_service import document_service
from app.services.project import project_service
from app.services.reports import report_service


def _dto_to_graphql_crew_member(dto: CrewMemberCreateDTO) -> CrewMember:
    """Helper for login response - minimal crew member."""
    return CrewMember(
        id=str(uuid.uuid4()),
        full_name=dto.full_name,
        email=dto.email if hasattr(dto, "email") else None,
    )


def _model_to_graphql_crew_member(model: CrewMemberModel) -> CrewMember:
    return CrewMember(
        id=model.id,
        full_name=model.full_name,
        nationality=model.nationality,
        country_of_residence=model.country_of_residence,
        date_of_birth=str(model.date_of_birth) if model.date_of_birth else None,
        gender=model.gender,
        languages=list(model.languages) if isinstance(model.languages, list) else None,
        flying_point=model.flying_point,
        email=model.email,
        phone=model.phone,
        role=model.role,
        publication_status=model.publication_status,
        passport=PassportInfo(
            number=model.passport_number,
            expiry=str(model.passport_expiry) if model.passport_expiry else None,
            issuing_country=model.passport_issuing_country,
        ),
        visa=VisaInfo(
            type=model.visa_type,
            restrictions=model.visa_restrictions,
            expiry=str(model.visa_expiry) if model.visa_expiry else None,
        ),
        medical=MedicalInfo(
            status=model.medical_status,
            expiry=str(model.medical_expiry) if model.medical_expiry else None,
            provider=model.medical_provider,
        ),
        insurance=InsuranceInfo(
            provider=model.insurance_provider,
            policy_number=model.insurance_policy_number,
            coverage=model.insurance_coverage,
            expiry=str(model.insurance_expiry) if model.insurance_expiry else None,
        ),
        availability_status=model.availability_status,
        availability_date=str(model.availability_date) if model.availability_date else None,
        profile_completeness_score=model.profile_completeness_score,
        years_of_experience=round(model.experience_months / 12, 1)
        if model.experience_months is not None
        else None,
        education=model.education,
        professional_summary=model.professional_summary,
        geographical_experience=json.dumps(model.geographical_experience)
        if model.geographical_experience
        else None,
        systems_experience=json.dumps(model.systems_experience)
        if model.systems_experience
        else None,
        training_qualifications=json.dumps(model.training_qualifications)
        if model.training_qualifications
        else None,
        work_history=[_model_to_graphql_work_history(w) for w in (model.work_history or [])],
        certifications=[_model_to_graphql_certification(c) for c in (model.certifications or [])],
        internal_notes=model.internal_notes,
        tags=json.dumps(model.tags) if model.tags else None,
        created_at=str(model.created_at),
        updated_at=str(model.updated_at),
    )


def _model_to_graphql_certification(model: CertificationModel) -> Certification:
    return Certification(
        id=model.id,
        cert_type=model.cert_type,
        cert_number=model.cert_number,
        issuing_body=model.issuing_body,
        issue_date=str(model.issue_date) if model.issue_date else None,
        expiry_date=str(model.expiry_date) if model.expiry_date else None,
        renewal_date=str(model.renewal_date) if model.renewal_date else None,
        status=model.status,
        document_ref=model.document_ref,
        extracted_confidence=model.extracted_confidence,
        verification_status=model.verification_status,
    )


def _model_to_graphql_work_history(model: WorkHistoryModel) -> WorkHistory:
    return WorkHistory(
        id=model.id,
        client_name=model.client_name,
        project_name=model.project_name,
        project_type=model.project_type,
        location=model.location,
        country=model.country,
        role=model.role,
        responsibilities=model.responsibilities,
        start_date=str(model.start_date) if model.start_date else None,
        end_date=str(model.end_date) if model.end_date else None,
        status=model.status,
    )


def _model_to_graphql_document(model: DocumentModel) -> DocumentType:
    return DocumentType(
        id=model.id,
        file_name=model.file_name,
        file_type=model.file_type,
        file_size=model.file_size,
        storage_type=model.storage_type,
        classification=model.classification,
        extraction_status=model.extraction_status,
        extracted_text=model.extracted_text,
        extracted_data=json.dumps(model.extracted_data) if model.extracted_data else None,
        extraction_confidence=json.dumps(model.extraction_confidence)
        if model.extraction_confidence
        else None,
        uploaded_by=model.uploaded_by,
        uploaded_at=str(model.uploaded_at),
        version_number=model.version_number,
    )


def _model_to_graphql_project(model: ProjectModel) -> Project:
    return Project(
        id=model.id,
        client_name=model.client_name,
        project_name=model.project_name,
        project_type=model.project_type,
        location=model.location,
        country=model.country,
        start_date=str(model.start_date) if model.start_date else None,
        end_date=str(model.end_date) if model.end_date else None,
        status=model.status,
        requirements=json.dumps(model.requirements) if model.requirements else None,
    )


def _model_to_graphql_vessel(model: VesselModel) -> VesselType:
    return VesselType(
        imo=model.imo,
        name=model.name,
        mmsi=model.mmsi,
        callsign=model.callsign,
        vessel_type=model.vessel_type,
        flag=model.flag,
        length=model.length,
        width=model.width,
        year_built=model.year_built,
        created_at=str(model.created_at),
        updated_at=str(model.updated_at),
    )


def _model_to_graphql_assignment(model: CampaignAssignmentModel) -> CampaignAssignmentType:
    from sqlalchemy.inspection import inspect as sa_inspect

    state = sa_inspect(model)
    crew_name = None
    if "crew_member" in state.dict and model.crew_member is not None:
        crew_name = model.crew_member.full_name
    elif "crew_member" not in state.unloaded:
        try:
            if model.crew_member:
                crew_name = model.crew_member.full_name
        except Exception:
            crew_name = None

    vessel_name = None
    if "vessel" in state.dict and model.vessel is not None:
        vessel_name = model.vessel.name
    elif "vessel" not in state.unloaded:
        try:
            if model.vessel:
                vessel_name = model.vessel.name
        except Exception:
            vessel_name = None

    project_name = None
    if "project" in state.dict and model.project is not None:
        project_name = model.project.project_name
    elif "project" not in state.unloaded:
        try:
            if model.project:
                project_name = model.project.project_name
        except Exception:
            project_name = None

    return CampaignAssignmentType(
        id=model.id,
        crew_member_id=model.crew_member_id,
        project_id=model.project_id,
        vessel_imo=model.vessel_imo,
        role_on_board=model.role_on_board,
        start_date=str(model.start_date),
        end_date=str(model.end_date),
        status=model.status,
        agreed_day_rate=model.agreed_day_rate,
        notes=model.notes,
        created_at=str(model.created_at),
        updated_at=str(model.updated_at),
        crew_name=crew_name,
        vessel_name=vessel_name,
        project_name=project_name,
    )


@strawberry.type
class Query:
    @strawberry.field
    @require_staff
    async def cv_reviews(self, info: Info, limit: int = 50, offset: int = 0) -> list[CVReviewType]:
        actor = info.context["current_user"]
        reviews = await cv_review_service.list_visible(
            actor_id=actor.id,
            actor_role=actor.role,
            limit=min(max(limit, 1), 100),
            offset=max(offset, 0),
        )
        return [
            CVReviewType(
                id=review.id,
                document_id=review.document_id,
                crew_member_id=review.crew_member_id,
                status=review.status,
                proposed_data=json.dumps(review.proposed_data) if review.proposed_data else None,
                approved_data=json.dumps(review.approved_data) if review.approved_data else None,
                submitted_by=review.submitted_by,
                reviewed_by=review.reviewed_by,
                review_note=review.review_note,
                created_at=str(review.created_at),
                reviewed_at=str(review.reviewed_at) if review.reviewed_at else None,
            )
            for review in reviews
        ]

    @strawberry.field
    @require_auth
    async def me(self, info: Info) -> Optional[CrewMember]:
        user = info.context.get("current_user")
        return _model_to_graphql_crew_member(user) if user else None

    @strawberry.field
    @require_auth
    async def crew_member(self, info: Info, id: str) -> Optional[CrewMember]:
        crew = await crew_service.get_crew_member(id)
        actor = info.context["current_user"]
        if (
            crew
            and crew.publication_status != "approved"
            and actor.role != "admin"
            and crew.submitted_by != actor.id
        ):
            return None
        if crew:
            await audit_service.log_profile_access(
                actor_id=actor.id, action="view_profile", crew_member_id=crew.id
            )
            tier = tier_for_role(actor.role)
            # Staff T2 scope: C2 visible only for own drafts or approved profiles.
            # For an approved profile T2 is fine; for another staff member's draft
            # the publication check above already returned None, so no leak.
            gql = _model_to_graphql_crew_member(crew)
            return scrub_crew_member(gql, tier)
        return None

    @strawberry.field
    @require_auth
    async def crew_members(
        self,
        info: Info,
        availability: Optional[AvailabilityStatus] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CrewMember]:
        # Enforce pagination limits to avoid abuse
        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)
        crew_list = await crew_service.list_crew_members(
            availability=availability.value if availability else None,
            search=search,
            limit=limit,
            offset=offset,
        )
        actor = info.context["current_user"]
        await audit_service.log_profile_access(
            actor_id=actor.id, action="list_profiles", result_count=len(crew_list)
        )
        tier = tier_for_role(actor.role)
        return [scrub_crew_member(_model_to_graphql_crew_member(c), tier) for c in crew_list]

    @strawberry.field
    @require_auth
    async def search_crew(self, info: Info, query: str) -> list[CrewMember]:
        crew_list = await crew_service.list_crew_members(search=query)
        actor = info.context["current_user"]
        await audit_service.log_profile_access(
            actor_id=actor.id, action="keyword_search", result_count=len(crew_list)
        )
        tier = tier_for_role(actor.role)
        return [scrub_crew_member(_model_to_graphql_crew_member(c), tier) for c in crew_list]

    @strawberry.field
    @require_staff
    async def expiring_certifications(
        self,
        info: Info,
        days: int = 30,
    ) -> list[Certification]:
        certs = await certification_service.get_expiring_certifications(days)
        actor = info.context["current_user"]
        tier = tier_for_role(actor.role)
        # Expiring certs carry cert_number/issuing_body (C2) — T2+ only.
        # Resolver is @require_staff so T1 never reaches here, but scrub still
        # enforces C3 denial for staff.
        from app.graphql.scrub import scrub_certification

        return [scrub_certification(_model_to_graphql_certification(c), tier) for c in certs]

    @strawberry.field
    @require_admin
    async def compliance_status(self, info: Info, crew_id: str) -> str:
        actor = info.context["current_user"]
        if not await crew_service.can_access_profile(
            crew_id, actor_id=actor.id, actor_role=actor.role
        ):
            raise ValueError("Crew member not found")
        status = await crew_service.get_compliance_status(crew_id)
        return json.dumps(status)

    @strawberry.field
    @require_auth
    async def crew_summary(self, info: Info, crew_id: str) -> str:
        from app.services.consultant_knowledge import consultant_knowledge_service

        factory = get_session_factory()
        async with factory() as session:
            return await consultant_knowledge_service.summarize(crew_id, db_session=session)

    @strawberry.field
    @require_auth
    async def document(self, info: Info, id: str) -> Optional[DocumentType]:
        doc = await document_service.get_document(id)
        actor = info.context["current_user"]
        if (
            doc
            and doc.crew_member_id
            and not await crew_service.can_access_profile(
                doc.crew_member_id, actor_id=actor.id, actor_role=actor.role
            )
        ):
            return None
        if not doc:
            return None
        tier = tier_for_role(actor.role)
        # T1 callers must not see document metadata at all (C2).
        if tier == "T1":
            return None
        gql = _model_to_graphql_document(doc)
        return scrub_document(gql, tier)

    @strawberry.field
    @require_auth
    async def documents_by_crew(self, info: Info, crew_id: str) -> list[DocumentType]:
        actor = info.context["current_user"]
        if not await crew_service.can_access_profile(
            crew_id, actor_id=actor.id, actor_role=actor.role
        ):
            return []
        tier = tier_for_role(actor.role)
        if tier == "T1":
            return []
        docs = await document_service.get_documents_by_crew(crew_id)
        return [scrub_document(_model_to_graphql_document(d), tier) for d in docs]

    @strawberry.field
    @require_admin
    async def pending_reviews(self, info: Info) -> list[DocumentType]:
        docs = await document_service.get_pending_documents()
        return [_model_to_graphql_document(d) for d in docs]

    @strawberry.field
    @require_auth
    async def query_crew(self, info: Info, query: str) -> CrewQueryResponse:
        from app.services.consultant_knowledge import consultant_knowledge_service

        factory = get_session_factory()
        async with factory() as session:
            search_result = await consultant_knowledge_service.search(
                query, db_session=session, mode="auto"
            )
        result = search_result.raw or {}
        actor = info.context["current_user"]
        await audit_service.log_profile_access(
            actor_id=actor.id,
            action="natural_search",
            result_count=len(result.get("results") or []),
        )

        return CrewQueryResponse(
            intent=result.get("intent", "general"),
            query=result.get("query", query),
            summary=result.get("summary", ""),
            results=json.dumps(result.get("results", [])) if result.get("results") else None,
            criteria=json.dumps(result.get("criteria", {})) if result.get("criteria") else None,
            total_issues=result.get("total_issues"),
            crew_id=result.get("crew_id"),
            crew_name=result.get("crew_name"),
        )

    @strawberry.field
    @require_auth
    async def project(self, info: Info, id: str) -> Optional[Project]:
        model = await project_service.get_project(id)
        if not model:
            return None
        actor = info.context["current_user"]
        tier = tier_for_role(actor.role)
        return scrub_project(_model_to_graphql_project(model), tier)

    @strawberry.field
    @require_auth
    async def projects(
        self,
        info: Info,
        status: Optional[ProjectStatus] = None,
    ) -> list[Project]:
        models = await project_service.list_projects(status.value if status else None)
        actor = info.context["current_user"]
        tier = tier_for_role(actor.role)
        return [scrub_project(_model_to_graphql_project(m), tier) for m in models]

    @strawberry.field
    @require_auth
    async def vessel_search(self, info: Info, name: str, limit: int = 20) -> VesselSearchResponse:
        """Search external AIS vessels via VesselAPI. Auth-gated, backend-owned key."""
        from app.services.vessel_api import (
            VesselApiNotConfiguredError,
            vessel_api_service,
        )

        # Input validation at the boundary - never trust a GraphQL string.
        trimmed = name.strip()
        if not trimmed:
            return VesselSearchResponse(
                vessels=[], cached=False, configured=vessel_api_service.is_configured()
            )
        # Clamp limit server-side regardless of client.
        limit = min(max(limit, 1), 50)
        try:
            result = await vessel_api_service.search_vessels(trimmed, limit=limit)
        except VesselApiNotConfiguredError:
            return VesselSearchResponse(vessels=[], cached=False, configured=False)
        except ValueError as exc:
            from graphql import GraphQLError as _GQLE

            raise _GQLE(str(exc), extensions={"code": "BAD_USER_INPUT"}) from exc
        except Exception as exc:
            from graphql import GraphQLError as _GQLE

            # Do not leak upstream body; log at service layer.
            raise _GQLE("Vessel search unavailable", extensions={"code": "UPSTREAM_ERROR"}) from exc
        return VesselSearchResponse(
            vessels=[VesselSummary(**s.__dict__) for s in result.vessels],
            cached=result.cached,
            upstream_count=result.upstream_count,
            configured=True,
        )

    @strawberry.field
    @require_auth
    async def vessel_position(
        self, info: Info, vessel_id: str, id_type: VesselIdType
    ) -> Optional[VesselPosition]:
        from app.services.vessel_api import (
            VesselApiNotConfiguredError,
            VesselApiNotFoundError,
            vessel_api_service,
        )

        if not vessel_id.strip():
            from graphql import GraphQLError as _GQLE

            raise _GQLE("vesselId must not be empty", extensions={"code": "BAD_USER_INPUT"})
        try:
            pos = await vessel_api_service.get_position(vessel_id.strip(), id_type=id_type.value)
        except VesselApiNotConfiguredError:
            from graphql import GraphQLError as _GQLE

            raise _GQLE(
                "Vessel tracking is not configured", extensions={"code": "NOT_CONFIGURED"}
            ) from None
        except VesselApiNotFoundError:
            return None
        except ValueError as exc:
            from graphql import GraphQLError as _GQLE

            raise _GQLE(str(exc), extensions={"code": "BAD_USER_INPUT"}) from exc
        return VesselPosition(**pos.__dict__)

    @strawberry.field
    @require_auth
    async def vessels_in_radius(
        self,
        info: Info,
        latitude: float,
        longitude: float,
        radius: int,
        limit: int = 20,
    ) -> VesselSearchResponse:
        from app.services.vessel_api import (
            VesselApiNotConfiguredError,
            vessel_api_service,
        )

        limit = min(max(limit, 1), 50)
        try:
            result = await vessel_api_service.vessels_in_radius(
                latitude=latitude, longitude=longitude, radius_m=radius, limit=limit
            )
        except VesselApiNotConfiguredError:
            return VesselSearchResponse(vessels=[], cached=False, configured=False)
        except ValueError as exc:
            from graphql import GraphQLError as _GQLE

            raise _GQLE(str(exc), extensions={"code": "BAD_USER_INPUT"}) from exc
        except Exception as exc:
            from graphql import GraphQLError as _GQLE

            raise _GQLE("Vessel lookup unavailable", extensions={"code": "UPSTREAM_ERROR"}) from exc
        return VesselSearchResponse(
            vessels=[VesselSummary(**s.__dict__) for s in result.vessels],
            cached=result.cached,
            upstream_count=result.upstream_count,
            configured=True,
        )

    @strawberry.field
    @require_auth
    async def campaign_assignments(
        self,
        info: Info,
        vessel_imo: Optional[str] = None,
        project_id: Optional[str] = None,
        crew_id: Optional[str] = None,
        status: Optional[CampaignAssignmentStatus] = None,
    ) -> list[CampaignAssignmentType]:
        from app.services.assignment import assignment_service

        status_val = status.value if status else None
        models = await assignment_service.list_assignments(
            vessel_imo=vessel_imo,
            project_id=project_id,
            crew_member_id=crew_id,
            status=status_val,
        )
        return [_model_to_graphql_assignment(m) for m in models]

    @strawberry.field
    @require_auth
    async def vessel_roster(
        self,
        info: Info,
        imo: str,
    ) -> list[CampaignAssignmentType]:
        from app.services.assignment import assignment_service

        models = await assignment_service.list_assignments(vessel_imo=imo)
        return [_model_to_graphql_assignment(m) for m in models]

    @strawberry.field
    @require_auth
    async def vessel_record(
        self,
        info: Info,
        imo: str,
    ) -> Optional[VesselType]:
        from app.services.assignment import assignment_service

        model = await assignment_service.get_vessel(imo)
        return _model_to_graphql_vessel(model) if model else None

    @strawberry.field
    @require_staff
    async def evaluate_assignment_compliance(
        self,
        info: Info,
        crew_member_id: str,
        start_date: str,
        end_date: str,
    ) -> AssignmentComplianceReportType:
        from datetime import date
        from graphql import GraphQLError
        from app.services.assignment import assignment_service

        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except Exception as exc:
            raise GraphQLError(f"Invalid date format: {exc}", extensions={"code": "BAD_USER_INPUT"}) from exc

        try:
            report = await assignment_service.evaluate_compliance(
                crew_member_id=crew_member_id,
                start_date=start,
                end_date=end,
            )
        except ValueError as exc:
            raise GraphQLError(str(exc), extensions={"code": "BAD_USER_INPUT"}) from exc

        checks = [
            ComplianceCheckItemType(
                item=c["item"],
                status=c["status"],
                detail=c["detail"],
            )
            for c in report["checks"]
        ]

        return AssignmentComplianceReportType(
            crew_member_id=report["crew_member_id"],
            crew_name=report["crew_name"],
            status=report["status"],
            has_conflict=report["has_conflict"],
            issues=report["issues"],
            checks=checks,
        )

    @strawberry.field
    @require_auth
    async def generate_report(
        self,
        info: Info,
        report_type: ReportType,
        filters: Optional[str] = None,
    ) -> Report:
        actor = info.context["current_user"]
        tier = tier_for_role(actor.role)
        # Compliance/performance/project_readiness carry C3 detail — T2+ only.
        if report_type in (
            ReportType.COMPLIANCE,
            ReportType.PERFORMANCE,
            ReportType.PROJECT_READINESS,
        ):
            if tier == "T1":
                from graphql import GraphQLError

                raise GraphQLError("Admin access required", extensions={"code": "FORBIDDEN"})

        filter_dict = json.loads(filters) if filters else {}

        factory = get_session_factory()
        async with factory() as session:
            data = await report_service.build_report_data(report_type.value, session)

        # Optionally enrich with LLM via report_service; fall back to deterministic summary
        try:
            ai_report = await report_service.generate_report(report_type.value, data, filter_dict)
            return Report(
                id=ai_report.get("id") or str(uuid.uuid4()),
                report_type=report_type.value,
                title=ai_report.get("title") or f"{report_type.value.title()} Report",
                generated_at=ai_report.get("generated_at")
                or datetime.now(timezone.utc).isoformat(),
                filters=filters,
                summary=ai_report.get("summary") or "Report generated successfully.",
                data=ai_report.get("data") or json.dumps(data),
                recommendations=ai_report.get("recommendations") or json.dumps([]),
            )
        except Exception:
            # Deterministic fallback if LLM unavailable
            summary = report_service.build_fallback_summary(report_type.value, data)
            return Report(
                id=str(uuid.uuid4()),
                report_type=report_type.value,
                title=f"{report_type.value.title()} Report",
                generated_at=datetime.now(timezone.utc).isoformat(),
                filters=filters,
                summary=summary,
                data=json.dumps(data),
                recommendations=json.dumps([]),
            )


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def login(self, info: Info, email: str, password: str) -> AuthPayload:
        from app.config import get_settings
        from app.services.cache import cache_service

        _s = get_settings()

        # Login-specific rate limiting: 5 attempts / 5 min per (ip, email_lower)
        request = info.context.get("request")
        client_ip = request.client.host if request and request.client else "unknown"
        login_key = f"login:{client_ip}:{email.lower()}"
        try:
            if await cache_service.is_redis_available():
                login_count = await cache_service.increment_rate_limit(login_key, 300)
                if login_count and login_count > 5:
                    from graphql import GraphQLError

                    raise GraphQLError(
                        "Too many login attempts. Please try again later.",
                        extensions={"code": "RATE_LIMITED"},
                    )
        except GraphQLError:
            raise
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Login rate limit check failed: {e}")

        result = await auth_service.authenticate(email, password)
        if result:
            token = result.get("token")
            # Set HttpOnly+Secure cookie on the real GraphQL response
            try:
                response = info.context.get("response")
                if response is not None and token:
                    is_secure = _s.APP_ENV == "production"
                    if hasattr(response, "set_cookie"):
                        response.set_cookie(
                            key=_s.SESSION_COOKIE_NAME,
                            value=token,
                            httponly=True,
                            secure=is_secure,
                            samesite="lax",
                            max_age=_s.SESSION_MAX_AGE,
                            path="/",
                        )
            except Exception:
                logger = logging.getLogger(__name__)
                logger.debug("Could not set session cookie on login response", exc_info=True)
            return AuthPayload(
                success=True,
                message="Login successful",
                token=token,
                user=CrewMember(
                    id=result["user"]["id"],
                    full_name=result["user"]["full_name"],
                    email=result["user"]["email"],
                    role=result["user"].get("role", "user"),
                ),
            )
        return AuthPayload(success=False, message="Invalid email or password")

    @strawberry.mutation
    @require_auth
    async def logout(self, info: Info) -> bool:
        response = info.context.get("response")
        if response is not None and hasattr(response, "delete_cookie"):
            from app.config import get_settings as _gs

            _s = _gs()
            response.delete_cookie(key=_s.SESSION_COOKIE_NAME, path="/")
        # Revoke the session token server-side (jti blocklist)
        from app.auth.decorators import _extract_token

        request = info.context.get("request")
        token = _extract_token(request) if request else None
        if token:
            from app.auth.session import revoke_session_token

            await revoke_session_token(token)
        return True

    @strawberry.mutation
    @require_staff
    async def create_crew_member(
        self,
        info: Info,
        full_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        nationality: Optional[str] = None,
        country_of_residence: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        gender: Optional[str] = None,
        languages: Optional[list[str]] = None,
        flying_point: Optional[str] = None,
        cv_submission: bool = False,
        confirm_distinct: bool = False,
    ) -> CrewMember:
        dto = CrewMemberCreateDTO(
            full_name=full_name,
            email=email,
            phone=phone,
            nationality=nationality,
            country_of_residence=country_of_residence,
            date_of_birth=date.fromisoformat(date_of_birth) if date_of_birth else None,
            gender=gender,
            languages=languages,
            flying_point=flying_point,
        )
        actor = info.context["current_user"]
        if actor.role == "staff" and not cv_submission:
            from graphql import GraphQLError

            raise GraphQLError(
                "Staff-created specialists require a CV submission",
                extensions={"code": "CV_REQUIRED"},
            )
        try:
            crew = await crew_service.create_crew_member(
                dto_to_crew_member_model(dto),
                as_draft=cv_submission,
                submitted_by=actor.id if cv_submission else None,
                allow_duplicate=actor.role == "admin" and confirm_distinct,
            )
        except PossibleDuplicateError as exc:
            from graphql import GraphQLError

            raise GraphQLError(
                str(exc),
                extensions={"code": "POSSIBLE_DUPLICATE", "candidateId": exc.candidate_id},
            ) from exc
        return _model_to_graphql_crew_member(crew)

    @strawberry.mutation
    @require_admin
    async def approve_cv_review(
        self,
        info: Info,
        review_id: str,
        approved_data: str,
        note: Optional[str] = None,
    ) -> bool:
        parsed = json.loads(approved_data)
        if not isinstance(parsed, dict):
            raise ValueError("Approved CV data must be an object")
        actor = info.context["current_user"]
        await cv_review_service.approve(
            review_id, approved_data=parsed, reviewer_id=actor.id, note=note
        )
        return True

    @strawberry.mutation
    @require_admin
    async def reject_cv_review(self, info: Info, review_id: str, note: str) -> bool:
        actor = info.context["current_user"]
        await cv_review_service.reject(review_id, reviewer_id=actor.id, note=note)
        return True

    @strawberry.mutation
    @require_admin
    async def set_staff_role(self, info: Info, user_id: str, enabled: bool) -> CrewMember:
        user = await crew_service.set_staff_role(user_id, enabled=enabled)
        return _model_to_graphql_crew_member(user)

    @strawberry.mutation
    @require_admin
    async def update_crew_member(
        self,
        info: Info,
        id: str,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        nationality: Optional[str] = None,
        country_of_residence: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        gender: Optional[str] = None,
        languages: Optional[list[str]] = None,
        flying_point: Optional[str] = None,
        availability_status: Optional[AvailabilityStatus] = None,
    ) -> CrewMember:
        dto = CrewMemberUpdateDTO(
            full_name=full_name,
            email=email,
            phone=phone,
            nationality=nationality,
            country_of_residence=country_of_residence,
            date_of_birth=date.fromisoformat(date_of_birth) if date_of_birth else None,
            gender=gender,
            languages=languages,
            flying_point=flying_point,
            availability_status=availability_status.value if availability_status else None,
        )
        crew = await crew_service.update_crew_member(id, dto.model_dump(exclude_none=True))
        return _model_to_graphql_crew_member(crew)

    @strawberry.mutation
    @require_admin
    async def delete_crew_member(self, info: Info, id: str) -> bool:
        """Permanently delete a crew member and their managed documents.

        This is intentionally admin-only.  Dropbox files are removed before
        database metadata so a failed remote deletion leaves the member and
        their documents recoverable.
        """
        current_user = info.context.get("current_user")
        requesting_user_id = current_user.id if current_user else None
        return await crew_service.delete_crew_member(id, requesting_user_id)

    @strawberry.mutation
    @require_admin
    async def upload_document(
        self,
        info: Info,
        crew_id: str,
        file_name: str,
        file_type: str,
        file_size: int,
        classification: Optional[DocumentClassification] = None,
    ) -> DocumentType:
        from app.config import get_settings
        from app.services.upload import safe_path_component

        _settings = get_settings()
        safe_crew_id = safe_path_component(crew_id, "crew_id")
        doc_id = str(uuid.uuid4())
        storage_path = (
            f"{_settings.DOCUMENT_STORAGE_PATH}/{safe_crew_id}/{doc_id}_{Path(file_name).name}"
        )

        dto = DocumentCreateDTO(
            crew_member_id=safe_crew_id,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            storage_path=storage_path,
            classification=classification.value if classification else None,
        )

        doc = await document_service.create_document(
            crew_id=safe_crew_id,
            file_name=dto.file_name,
            file_type=dto.file_type,
            file_size=dto.file_size,
            storage_path=dto.storage_path,
            classification=dto.classification,
        )
        return _model_to_graphql_document(doc)

    @strawberry.mutation
    @require_admin
    async def confirm_extraction(
        self,
        info: Info,
        document_id: str,
        data: str,
    ) -> DocumentType:
        confirmed = await document_service.confirm_extraction(document_id, json.loads(data))
        if not confirmed:
            raise ValueError(f"Document {document_id} not found")
        return _model_to_graphql_document(confirmed)

    @strawberry.mutation
    @require_admin
    async def reprocess_document(self, info: Info, document_id: str) -> DocumentType:
        doc = await document_service.reprocess_document(document_id)
        return _model_to_graphql_document(doc)

    @strawberry.mutation
    @require_admin
    async def confirm_document_match(
        self,
        info: Info,
        document_id: str,
        crew_id: str,
    ) -> DocumentType:
        doc = await document_service.link_to_crew_member(document_id, crew_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        return _model_to_graphql_document(doc)

    @strawberry.mutation
    @require_admin
    async def add_certification(
        self,
        info: Info,
        crew_id: str,
        cert_type: CertType,
        cert_number: Optional[str] = None,
        issuing_body: Optional[str] = None,
        issue_date: Optional[str] = None,
        expiry_date: Optional[str] = None,
    ) -> Certification:
        dto = CertificationCreateDTO(
            crew_member_id=crew_id,
            cert_type=cert_type.value,
            cert_number=cert_number,
            issuing_body=issuing_body,
            issue_date=date.fromisoformat(issue_date) if issue_date else None,
            expiry_date=date.fromisoformat(expiry_date) if expiry_date else None,
        )
        cert = await certification_service.add_certification(
            crew_id=dto.crew_member_id,
            cert_type=dto.cert_type,
            cert_number=dto.cert_number,
            issuing_body=dto.issuing_body,
            issue_date=dto.issue_date,
            expiry_date=dto.expiry_date,
        )
        return _model_to_graphql_certification(cert)

    @strawberry.mutation
    @require_admin
    async def update_certification(
        self,
        info: Info,
        id: str,
        status: Optional[CertStatus] = None,
    ) -> Certification:
        cert = await certification_service.update_certification(
            id, status.value if status else None
        )
        return _model_to_graphql_certification(cert)

    @strawberry.mutation
    @require_admin
    async def verify_certification(
        self,
        info: Info,
        id: str,
        status: VerificationStatus,
    ) -> Certification:
        cert = await certification_service.verify_certification(id, status.value)
        return _model_to_graphql_certification(cert)

    @strawberry.mutation
    @require_admin
    async def create_project(
        self,
        info: Info,
        client_name: str,
        project_name: str,
        project_type: ProjectType,
    ) -> Project:
        dto = ProjectCreateDTO(
            client_name=client_name,
            project_name=project_name,
            project_type=project_type.value,
        )
        project = await project_service.create_project(dto_to_project_model(dto))
        return _model_to_graphql_project(project)

    @strawberry.mutation
    @require_admin
    async def update_project(
        self,
        info: Info,
        id: str,
        status: Optional[ProjectStatus] = None,
    ) -> Project:
        project = await project_service.update_project(id, status.value if status else None)
        return _model_to_graphql_project(project)

    @strawberry.mutation
    @require_admin
    async def assign_crew_to_project(
        self,
        info: Info,
        project_id: str,
        crew_ids: list[str],
    ) -> Project:
        project = await project_service.assign_crew(project_id, crew_ids)
        return _model_to_graphql_project(project)

    @strawberry.mutation
    @require_admin
    async def upload_cv_and_extract(
        self,
        info: Info,
        crew_id: str,
        file_name: str,
        file_type: str,
        file_size: int,
    ) -> CVExtractionResult:
        """Reject the retired metadata-only CV extraction API.

        A GraphQL variable call only carried file metadata, so no file ever
        existed at the extraction path.  Clients must use the multipart REST
        upload endpoint, which persists the binary before queuing extraction.
        """
        from graphql import GraphQLError

        raise GraphQLError(
            "uploadCvAndExtract is retired. Upload the CV binary to "
            "/api/documents/upload with classification 'cv'.",
            extensions={"code": "BAD_USER_INPUT"},
        )

    @strawberry.mutation
    @require_staff
    async def create_campaign_assignment(
        self,
        info: Info,
        input: CreateCampaignAssignmentInput,
    ) -> CampaignAssignmentType:
        from datetime import date

        from graphql import GraphQLError

        from app.services.assignment import assignment_service

        try:
            start = date.fromisoformat(input.start_date)
            end = date.fromisoformat(input.end_date)
        except Exception as exc:
            raise GraphQLError(f"Invalid date format: {exc}", extensions={"code": "BAD_USER_INPUT"}) from exc

        status_val = input.status.value if input.status else "proposed"

        try:
            model = await assignment_service.create_assignment(
                crew_member_id=input.crew_member_id,
                vessel_imo=input.vessel_imo,
                role_on_board=input.role_on_board,
                start_date=start,
                end_date=end,
                project_id=input.project_id,
                vessel_name=input.vessel_name,
                agreed_day_rate=input.agreed_day_rate,
                notes=input.notes,
                status=status_val,
            )
        except ValueError as exc:
            raise GraphQLError(str(exc), extensions={"code": "BAD_USER_INPUT"}) from exc

        return _model_to_graphql_assignment(model)

    @strawberry.mutation
    @require_staff
    async def update_campaign_assignment_status(
        self,
        info: Info,
        assignment_id: str,
        status: CampaignAssignmentStatus,
    ) -> CampaignAssignmentType:
        from graphql import GraphQLError

        from app.services.assignment import assignment_service

        try:
            model = await assignment_service.update_status(assignment_id, status.value)
        except ValueError as exc:
            raise GraphQLError(str(exc), extensions={"code": "BAD_USER_INPUT"}) from exc

        return _model_to_graphql_assignment(model)
