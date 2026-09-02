from __future__ import annotations

from app.graphql.dtos import (
    CertificationCreateDTO,
    CertificationDTO,
    CrewMemberCreateDTO,
    CrewMemberDTO,
    DocumentCreateDTO,
    DocumentDTO,
    InsuranceInfoDTO,
    MedicalInfoDTO,
    PassportInfoDTO,
    ProjectCreateDTO,
    ProjectDTO,
    VisaInfoDTO,
    WorkHistoryCreateDTO,
    WorkHistoryDTO,
)
from app.models import Certification as CertificationModel
from app.models import CrewMember as CrewMemberModel
from app.models import Document as DocumentModel
from app.models import Project as ProjectModel
from app.models import WorkHistory as WorkHistoryModel


def crew_member_to_dto(model: CrewMemberModel) -> CrewMemberDTO:
    return CrewMemberDTO(
        id=model.id,
        full_name=model.full_name,
        nationality=model.nationality,
        date_of_birth=model.date_of_birth,
        email=model.email,
        phone=model.phone,
        passport=PassportInfoDTO(
            number=model.passport_number,
            expiry=model.passport_expiry,
            issuing_country=model.passport_issuing_country,
        )
        if model.passport_number or model.passport_expiry
        else None,
        visa=VisaInfoDTO(
            type=model.visa_type,
            restrictions=model.visa_restrictions,
            expiry=model.visa_expiry,
        )
        if model.visa_type or model.visa_expiry
        else None,
        medical=MedicalInfoDTO(
            status=model.medical_status,
            expiry=model.medical_expiry,
            provider=model.medical_provider,
        )
        if model.medical_status or model.medical_expiry
        else None,
        insurance=InsuranceInfoDTO(
            provider=model.insurance_provider,
            policy_number=model.insurance_policy_number,
            coverage=model.insurance_coverage,
            expiry=model.insurance_expiry,
        )
        if model.insurance_provider or model.insurance_expiry
        else None,
        availability_status=model.availability_status or "available",
        availability_date=model.availability_date,
        profile_completeness_score=model.profile_completeness_score,
        internal_notes=model.internal_notes,
        tags=model.tags,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def certification_to_dto(model: CertificationModel) -> CertificationDTO:
    return CertificationDTO(
        id=model.id,
        crew_member_id=model.crew_member_id,
        cert_type=model.cert_type,
        cert_number=model.cert_number,
        issuing_body=model.issuing_body,
        issue_date=model.issue_date,
        expiry_date=model.expiry_date,
        renewal_date=model.renewal_date,
        status=model.status or "pending_verification",
        document_ref=model.document_ref,
        extracted_confidence=model.extracted_confidence,
        verification_status=model.verification_status or "unverified",
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def work_history_to_dto(model: WorkHistoryModel) -> WorkHistoryDTO:
    return WorkHistoryDTO(
        id=model.id,
        crew_member_id=model.crew_member_id,
        client_name=model.client_name,
        project_name=model.project_name,
        project_type=model.project_type,
        location=model.location,
        country=model.country,
        role=model.role,
        responsibilities=model.responsibilities,
        start_date=model.start_date,
        end_date=model.end_date,
        status=model.status,
        document_ref=model.document_ref,
    )


def project_to_dto(model: ProjectModel) -> ProjectDTO:
    return ProjectDTO(
        id=model.id,
        client_name=model.client_name,
        project_name=model.project_name,
        project_type=model.project_type,
        location=model.location,
        country=model.country,
        water_depth=model.water_depth,
        start_date=model.start_date,
        end_date=model.end_date,
        status=model.status or "planning",
        crew_assigned=model.crew_assigned,
        requirements=model.requirements,
        document_ref=model.document_ref,
    )


def document_to_dto(model: DocumentModel) -> DocumentDTO:
    return DocumentDTO(
        id=model.id,
        crew_member_id=model.crew_member_id,
        file_name=model.file_name,
        file_type=model.file_type,
        file_size=model.file_size,
        storage_type=model.storage_type,
        storage_path=model.storage_path,
        dropbox_path=model.dropbox_path,
        dropbox_revision=model.dropbox_revision,
        classification=model.classification,
        classification_confidence=model.classification_confidence,
        extraction_status=model.extraction_status or "pending",
        extracted_data=model.extracted_data,
        extraction_confidence=model.extraction_confidence,
        uploaded_by=model.uploaded_by,
        uploaded_at=model.uploaded_at,
        version_number=model.version_number or 1,
        previous_version_id=model.previous_version_id,
    )


def dto_to_crew_member_model(dto: CrewMemberCreateDTO) -> CrewMemberModel:
    return CrewMemberModel(
        full_name=dto.full_name,
        email=dto.email,
        phone=dto.phone,
        nationality=dto.nationality,
        country_of_residence=dto.country_of_residence,
        date_of_birth=dto.date_of_birth,
        gender=dto.gender,
        languages=dto.languages,
        flying_point=dto.flying_point,
        passport_number=dto.passport.number if dto.passport else None,
        passport_expiry=dto.passport.expiry if dto.passport else None,
        passport_issuing_country=dto.passport.issuing_country if dto.passport else None,
        visa_type=dto.visa.type if dto.visa else None,
        visa_restrictions=dto.visa.restrictions if dto.visa else None,
        visa_expiry=dto.visa.expiry if dto.visa else None,
        medical_status=dto.medical.status if dto.medical else None,
        medical_expiry=dto.medical.expiry if dto.medical else None,
        medical_provider=dto.medical.provider if dto.medical else None,
        insurance_provider=dto.insurance.provider if dto.insurance else None,
        insurance_policy_number=dto.insurance.policy_number if dto.insurance else None,
        insurance_coverage=dto.insurance.coverage if dto.insurance else None,
        insurance_expiry=dto.insurance.expiry if dto.insurance else None,
        availability_status=dto.availability_status,
        internal_notes=dto.internal_notes,
        tags=dto.tags,
    )


def dto_to_certification_model(dto: CertificationCreateDTO) -> CertificationModel:
    return CertificationModel(
        crew_member_id=dto.crew_member_id,
        cert_type=dto.cert_type,
        cert_number=dto.cert_number,
        issuing_body=dto.issuing_body,
        issue_date=dto.issue_date,
        expiry_date=dto.expiry_date,
        renewal_date=dto.renewal_date,
        document_ref=dto.document_ref,
    )


def dto_to_work_history_model(dto: WorkHistoryCreateDTO) -> WorkHistoryModel:
    return WorkHistoryModel(
        crew_member_id=dto.crew_member_id,
        client_name=dto.client_name,
        project_name=dto.project_name,
        project_type=dto.project_type,
        location=dto.location,
        country=dto.country,
        role=dto.role,
        responsibilities=dto.responsibilities,
        start_date=dto.start_date,
        end_date=dto.end_date,
        status=dto.status,
        document_ref=dto.document_ref,
    )


def dto_to_project_model(dto: ProjectCreateDTO) -> ProjectModel:
    return ProjectModel(
        client_name=dto.client_name,
        project_name=dto.project_name,
        project_type=dto.project_type,
        location=dto.location,
        country=dto.country,
        water_depth=dto.water_depth,
        start_date=dto.start_date,
        end_date=dto.end_date,
        requirements=dto.requirements,
    )


def dto_to_document_model(dto: DocumentCreateDTO) -> DocumentModel:
    return DocumentModel(
        crew_member_id=dto.crew_member_id,
        file_name=dto.file_name,
        file_type=dto.file_type,
        file_size=dto.file_size,
        storage_type=dto.storage_type,
        storage_path=dto.storage_path,
        classification=dto.classification,
        uploaded_by=dto.uploaded_by,
    )
