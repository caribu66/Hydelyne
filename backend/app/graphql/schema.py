from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import strawberry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from strawberry import Info

from app.auth.decorators import require_admin, require_auth
from app.database import get_session_factory
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
from app.graphql.types import (
    AuthPayload,
    AvailabilityStatus,
    Certification,
    CertStatus,
    CertType,
    CrewMember,
    CrewQueryResponse,
    CVExtractionResult,
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
    VisaInfo,
    WorkHistory,
)
from app.models import Certification as CertificationModel
from app.models import CrewMember as CrewMemberModel
from app.models import Document as DocumentModel
from app.models import Project as ProjectModel
from app.models import WorkHistory as WorkHistoryModel
from app.services.crew import auth_service, certification_service, crew_service
from app.services.document_service import document_service
from app.services.reports import report_service
from app.services.upload import document_upload_service


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


async def _reload_crew_with_relations(session: AsyncSession, crew_id: str) -> CrewMemberModel:
    """Re-fetch a crew member with work_history/certifications eager-loaded.

    `_model_to_graphql_crew_member` accesses these relationships synchronously;
    without selectinload here that lazy-loads outside the async greenlet
    context and raises `MissingGreenlet`.
    """
    stmt = (
        select(CrewMemberModel)
        .options(
            selectinload(CrewMemberModel.work_history),
            selectinload(CrewMemberModel.certifications),
        )
        .where(CrewMemberModel.id == crew_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


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


@strawberry.type
class Query:
    @strawberry.field
    @require_auth
    async def me(self, info: Info) -> Optional[CrewMember]:
        user = info.context.get("current_user")
        return _model_to_graphql_crew_member(user) if user else None

    @strawberry.field
    @require_auth
    async def crew_member(self, info: Info, id: str) -> Optional[CrewMember]:
        crew = await crew_service.get_crew_member(id)
        return _model_to_graphql_crew_member(crew) if crew else None

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
        return [_model_to_graphql_crew_member(c) for c in crew_list]

    @strawberry.field
    @require_auth
    async def search_crew(self, info: Info, query: str) -> list[CrewMember]:
        crew_list = await crew_service.list_crew_members(search=query)
        return [_model_to_graphql_crew_member(c) for c in crew_list]

    @strawberry.field
    @require_auth
    async def expiring_certifications(
        self,
        info: Info,
        days: int = 30,
    ) -> list[Certification]:
        certs = await certification_service.get_expiring_certifications(days)
        return [_model_to_graphql_certification(c) for c in certs]

    @strawberry.field
    @require_auth
    async def compliance_status(self, info: Info, crew_id: str) -> str:
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
        return _model_to_graphql_document(doc) if doc else None

    @strawberry.field
    @require_auth
    async def documents_by_crew(self, info: Info, crew_id: str) -> list[DocumentType]:
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.crew_member_id == crew_id)
            result = await session.execute(stmt)
            return [_model_to_graphql_document(d) for d in result.scalars().all()]

    @strawberry.field
    @require_auth
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
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(ProjectModel).where(ProjectModel.id == id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return _model_to_graphql_project(model) if model else None

    @strawberry.field
    @require_auth
    async def projects(
        self,
        info: Info,
        status: Optional[ProjectStatus] = None,
    ) -> list[Project]:
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(ProjectModel)
            if status:
                stmt = stmt.where(ProjectModel.status == status.value)
            result = await session.execute(stmt)
            return [_model_to_graphql_project(m) for m in result.scalars().all()]

    @strawberry.field
    @require_auth
    async def generate_report(
        self,
        info: Info,
        report_type: ReportType,
        filters: Optional[str] = None,
    ) -> Report:
        filter_dict = json.loads(filters) if filters else {}

        factory = get_session_factory()
        async with factory() as session:
            # Build report data deterministically first
            if report_type == ReportType.AVAILABILITY:
                stmt = select(CrewMemberModel).where(
                    CrewMemberModel.availability_status == "available"
                )
                result = await session.execute(stmt)
                crew_list = result.scalars().all()
                data = {
                    "available_count": len(crew_list),
                    "crew": [{"id": c.id, "name": c.full_name} for c in crew_list],
                }
            elif report_type == ReportType.COMPLIANCE:
                stmt = select(CertificationModel).where(
                    CertificationModel.status.in_(["expired", "expiring_soon"])
                )
                result = await session.execute(stmt)
                certs = result.scalars().all()
                data = {
                    "non_compliant_count": len(certs),
                    "certifications": [
                        {
                            "id": c.id,
                            "type": c.cert_type,
                            "status": c.status,
                            "expiry": str(c.expiry_date) if c.expiry_date else None,
                        }
                        for c in certs
                    ],
                }
            elif report_type == ReportType.PROJECT_READINESS:
                stmt = select(ProjectModel)
                result = await session.execute(stmt)
                projects = result.scalars().all()
                data = {
                    "project_count": len(projects),
                    "projects": [
                        {
                            "id": p.id,
                            "name": p.project_name,
                            "client": p.client_name,
                            "status": p.status,
                            "crew_assigned": (p.crew_assigned or []),
                        }
                        for p in projects
                    ],
                }
            else:  # PERFORMANCE
                # Note: performance data lives in document extracted_data; summarize what we have
                stmt = select(DocumentModel).where(DocumentModel.classification == "performance")
                result = await session.execute(stmt)
                perf_docs = result.scalars().all()
                data = {
                    "performance_document_count": len(perf_docs),
                    "documents": [
                        {
                            "id": d.id,
                            "file_name": d.file_name,
                            "extraction_status": d.extraction_status,
                        }
                        for d in perf_docs
                    ],
                }

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
            if report_type == ReportType.AVAILABILITY:
                summary = f"{data.get('available_count', 0)} crew members currently available."
            elif report_type == ReportType.COMPLIANCE:
                summary = f"{data.get('non_compliant_count', 0)} certifications require attention."
            else:
                summary = f"{report_type.value.title()} report generated successfully."
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
    @require_admin
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
    ) -> CrewMember:
        dto = CrewMemberCreateDTO(
            full_name=full_name,
            email=email,
            phone=phone,
            nationality=nationality,
            country_of_residence=country_of_residence,
            date_of_birth=date_of_birth,
            gender=gender,
            languages=languages,
            flying_point=flying_point,
        )
        factory = get_session_factory()
        async with factory() as session:
            crew = dto_to_crew_member_model(dto)
            session.add(crew)
            await session.commit()
            crew = await _reload_crew_with_relations(session, crew.id)
            graphql_crew = _model_to_graphql_crew_member(crew)

        from app.services.consultant_knowledge import consultant_knowledge_service

        await consultant_knowledge_service.index_crew_member(crew)
        return graphql_crew

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
            date_of_birth=date_of_birth,
            gender=gender,
            languages=languages,
            flying_point=flying_point,
            availability_status=availability_status.value if availability_status else None,
        )
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CrewMemberModel).where(CrewMemberModel.id == id)
            result = await session.execute(stmt)
            crew = result.scalar_one_or_none()
            if not crew:
                raise ValueError(f"Crew member {id} not found")
            if dto.full_name is not None:
                crew.full_name = dto.full_name
            if dto.email is not None:
                crew.email = dto.email
            if dto.phone is not None:
                crew.phone = dto.phone
            if dto.nationality is not None:
                crew.nationality = dto.nationality
            if dto.country_of_residence is not None:
                crew.country_of_residence = dto.country_of_residence
            if dto.date_of_birth is not None:
                crew.date_of_birth = dto.date_of_birth
            if dto.gender is not None:
                crew.gender = dto.gender
            if dto.languages is not None:
                crew.languages = dto.languages
            if dto.flying_point is not None:
                crew.flying_point = dto.flying_point
            if dto.availability_status is not None:
                crew.availability_status = dto.availability_status
            await session.commit()
            crew = await _reload_crew_with_relations(session, crew.id)
            graphql_crew = _model_to_graphql_crew_member(crew)

        from app.services.cache import cache_service
        from app.services.consultant_knowledge import consultant_knowledge_service

        await consultant_knowledge_service.index_crew_member(crew)
        # The AI summary is generated from these same fields — a stale
        # cached summary after an edit would show outdated facts.
        await cache_service.delete(cache_service._make_key("summary", crew.id))
        return graphql_crew

    @strawberry.mutation
    @require_admin
    async def delete_crew_member(self, info: Info, id: str) -> bool:
        """Permanently delete a crew member and their managed documents.

        This is intentionally admin-only.  Dropbox files are removed before
        database metadata so a failed remote deletion leaves the member and
        their documents recoverable.
        """
        current_user = info.context.get("current_user")
        if current_user and current_user.id == id:
            raise ValueError("You cannot delete your own administrator account")

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CrewMemberModel).where(CrewMemberModel.id == id)
            result = await session.execute(stmt)
            crew = result.scalar_one_or_none()
            if not crew:
                return False

            documents_result = await session.execute(
                select(DocumentModel).where(DocumentModel.crew_member_id == id)
            )
            documents = list(documents_result.scalars().all())

            # Keep all metadata when Dropbox cannot confirm deletion.
            for document in documents:
                if document.storage_type == "dropbox":
                    if (
                        not document.dropbox_path
                        or not await document_upload_service.delete_from_dropbox(
                            document.dropbox_path
                        )
                    ):
                        raise ValueError(
                            f"Could not delete Dropbox file for {document.file_name}; crew member was retained"
                        )

            for document in documents:
                await session.delete(document)
            await session.delete(crew)
            await session.commit()

        # Cache removal is best-effort and happens only after the database
        # transaction has succeeded. The "summary" and "compliance" keys are
        # addressable directly by crew_id via crewSummary/complianceStatus,
        # independent of whether the crew record still exists — a stale hit
        # there would keep serving a deleted person's data until its TTL
        # expires, so they must be cleared explicitly rather than assumed
        # unreachable.
        for document in documents:
            document_upload_service.delete_file(document.storage_path)

        from app.services.cache import cache_service
        from app.services.consultant_knowledge import consultant_knowledge_service

        await cache_service.delete(cache_service._make_key("crew", id))
        await cache_service.delete(cache_service._make_key("summary", id))
        await cache_service.delete(cache_service._make_key("compliance", id))
        await cache_service.invalidate_pattern("hydenlyne:crew_list:*")
        await consultant_knowledge_service.remove_from_index(id)
        return True

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
            crew_id=dto.crew_member_id,
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
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(DocumentModel).where(DocumentModel.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            if not doc:
                raise ValueError(f"Document {document_id} not found")
            doc.extraction_status = "pending"
            await session.commit()
            await session.refresh(doc)
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
        from datetime import date

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
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CertificationModel).where(CertificationModel.id == id)
            result = await session.execute(stmt)
            cert = result.scalar_one_or_none()
            if not cert:
                raise ValueError(f"Certification {id} not found")
            if status is not None:
                cert.status = status.value
            await session.commit()
            await session.refresh(cert)
            return _model_to_graphql_certification(cert)

    @strawberry.mutation
    @require_admin
    async def verify_certification(
        self,
        info: Info,
        id: str,
        status: VerificationStatus,
    ) -> Certification:
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CertificationModel).where(CertificationModel.id == id)
            result = await session.execute(stmt)
            cert = result.scalar_one_or_none()
            if not cert:
                raise ValueError(f"Certification {id} not found")
            cert.verification_status = status.value
            await session.commit()
            await session.refresh(cert)
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
        factory = get_session_factory()
        async with factory() as session:
            project = dto_to_project_model(dto)
            session.add(project)
            await session.commit()
            await session.refresh(project)
            return _model_to_graphql_project(project)

    @strawberry.mutation
    @require_admin
    async def update_project(
        self,
        info: Info,
        id: str,
        status: Optional[ProjectStatus] = None,
    ) -> Project:
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(ProjectModel).where(ProjectModel.id == id)
            result = await session.execute(stmt)
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {id} not found")
            if status is not None:
                project.status = status.value
            await session.commit()
            await session.refresh(project)
            return _model_to_graphql_project(project)

    @strawberry.mutation
    @require_admin
    async def assign_crew_to_project(
        self,
        info: Info,
        project_id: str,
        crew_ids: list[str],
    ) -> Project:
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(ProjectModel).where(ProjectModel.id == project_id)
            result = await session.execute(stmt)
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            project.crew_assigned = crew_ids
            await session.commit()
            await session.refresh(project)
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

        # Kept below temporarily as unreachable migration reference; remove
        # with the GraphQL field in the next breaking schema release.
        from app.services.cv_processing import cv_processing_service
        from app.services.extraction import extraction_service
        from app.services.text_extraction import text_extraction_service

        factory = get_session_factory()
        async with factory() as session:
            from app.services.upload import safe_path_component

            safe_crew_id = safe_path_component(crew_id, "crew_id")
            stmt = select(CrewMemberModel).where(CrewMemberModel.id == safe_crew_id)
            result = await session.execute(stmt)
            crew = result.scalar_one_or_none()
            if not crew:
                raise ValueError(f"Crew member {safe_crew_id} not found")

            doc_id = str(uuid.uuid4())
            storage_path = f"./data/documents/{safe_crew_id}/{doc_id}_{Path(file_name).name}"

            doc = DocumentModel(
                id=doc_id,
                crew_member_id=safe_crew_id,
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                storage_type="local",
                storage_path=storage_path,
                classification="cv",
                extraction_status="pending",
                uploaded_by="agent",
            )
            session.add(doc)
            await session.commit()

        extracted_data = {"skills": [], "specializations": [], "work_history": []}
        certs_created = 0
        work_history_created = 0

        try:
            mime_to_type = {
                "application/pdf": "pdf",
                "application/msword": "doc",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                "image/jpeg": "jpg",
                "image/png": "png",
                "message/rfc822": "eml",
                "application/vnd.ms-outlook": "msg",
            }
            extract_type = mime_to_type.get(
                file_type, file_type.split("/")[-1] if "/" in file_type else file_type
            )
            raw_text = text_extraction_service.extract_text_sync(storage_path, extract_type)
            extraction_result = extraction_service.extract_document_sync(raw_text, "cv")
            extracted_data = extraction_result

            processing_result = await cv_processing_service.process_cv_extraction(
                crew_id, extracted_data, doc_id
            )
            certs_created = processing_result.get("certifications_created", 0)
            work_history_created = processing_result.get("work_history_created", 0)

            async with factory() as session:
                stmt = select(DocumentModel).where(DocumentModel.id == doc_id)
                result = await session.execute(stmt)
                doc_record = result.scalar_one_or_none()
                if doc_record:
                    doc_record.extracted_data = extraction_result
                    doc_record.extraction_status = "extracted"
                    await session.commit()

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"CV extraction failed for {doc_id}: {e}")

        return CVExtractionResult(
            document_id=doc_id,
            crew_id=crew_id,
            status="extracted",
            certifications_created=certs_created,
            work_history_created=work_history_created,
            skills_found=extracted_data.get("skills", []),
            specializations_found=extracted_data.get("specializations", []),
        )
