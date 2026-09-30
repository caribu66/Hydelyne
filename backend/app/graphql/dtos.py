from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class PassportInfoDTO(BaseModel):
    number: Optional[str] = None
    expiry: Optional[date] = None
    issuing_country: Optional[str] = None


class VisaInfoDTO(BaseModel):
    type: Optional[str] = None
    restrictions: Optional[str] = None
    expiry: Optional[date] = None


class MedicalInfoDTO(BaseModel):
    status: Optional[str] = None
    expiry: Optional[date] = None
    provider: Optional[str] = None


class InsuranceInfoDTO(BaseModel):
    provider: Optional[str] = None
    policy_number: Optional[str] = None
    coverage: Optional[str] = None
    expiry: Optional[date] = None


class CrewMemberDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    full_name: str
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    languages: Optional[list[str]] = None
    flying_point: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    passport: Optional[PassportInfoDTO] = None
    visa: Optional[VisaInfoDTO] = None
    medical: Optional[MedicalInfoDTO] = None
    insurance: Optional[InsuranceInfoDTO] = None
    # Fail-closed like the persistence default: omitted availability is not
    # evidence of mobilizability.
    availability_status: str = "unavailable"
    availability_date: Optional[date] = None
    profile_completeness_score: Optional[float] = None
    internal_notes: Optional[str] = None
    tags: Optional[list[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CrewMemberCreateDTO(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    nationality: Optional[str] = Field(None, max_length=100)
    country_of_residence: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=50)
    languages: Optional[list[Annotated[str, Field(max_length=255)]]] = Field(None, max_length=100)
    flying_point: Optional[str] = Field(None, max_length=255)
    passport: Optional[PassportInfoDTO] = None
    visa: Optional[VisaInfoDTO] = None
    medical: Optional[MedicalInfoDTO] = None
    insurance: Optional[InsuranceInfoDTO] = None
    # Fail-closed like the persistence default: omitted availability is not
    # evidence of mobilizability.
    availability_status: str = "unavailable"
    internal_notes: Optional[str] = None
    tags: Optional[list[str]] = None


class CrewMemberUpdateDTO(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    nationality: Optional[str] = Field(None, max_length=100)
    country_of_residence: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=50)
    languages: Optional[list[Annotated[str, Field(max_length=255)]]] = Field(None, max_length=100)
    flying_point: Optional[str] = Field(None, max_length=255)
    availability_status: Optional[str] = None
    internal_notes: Optional[str] = None
    tags: Optional[list[str]] = None


class CertificationDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    crew_member_id: str
    cert_type: str
    cert_number: Optional[str] = None
    issuing_body: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    renewal_date: Optional[date] = None
    status: str = "pending_verification"
    document_ref: Optional[str] = None
    extracted_confidence: Optional[float] = None
    verification_status: str = "unverified"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CertificationCreateDTO(BaseModel):
    crew_member_id: str
    cert_type: str
    cert_number: Optional[str] = Field(None, max_length=100)
    issuing_body: Optional[str] = Field(None, max_length=255)
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    renewal_date: Optional[date] = None
    document_ref: Optional[str] = None


class CertificationUpdateDTO(BaseModel):
    status: Optional[str] = None
    verification_status: Optional[str] = None
    cert_number: Optional[str] = None
    issuing_body: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    renewal_date: Optional[date] = None


class WorkHistoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    crew_member_id: str
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    project_type: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    role: Optional[str] = None
    responsibilities: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    document_ref: Optional[str] = None


class WorkHistoryCreateDTO(BaseModel):
    crew_member_id: str
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    project_type: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    role: Optional[str] = None
    responsibilities: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    document_ref: Optional[str] = None


class ProjectDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    client_name: str
    project_name: str
    project_type: str
    location: Optional[str] = None
    country: Optional[str] = None
    water_depth: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = "planning"
    crew_assigned: Optional[list[str]] = None
    requirements: Optional[dict[str, Any]] = None
    document_ref: Optional[str] = None


class ProjectCreateDTO(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=255)
    project_name: str = Field(..., min_length=1, max_length=255)
    project_type: str
    location: Optional[str] = None
    country: Optional[str] = None
    water_depth: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    requirements: Optional[dict[str, Any]] = None


class ProjectUpdateDTO(BaseModel):
    status: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    crew_assigned: Optional[list[str]] = None
    requirements: Optional[dict[str, Any]] = None


class DocumentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    crew_member_id: Optional[str] = None
    file_name: str
    file_type: str
    file_size: int
    storage_type: str
    storage_path: str
    dropbox_path: Optional[str] = None
    dropbox_revision: Optional[str] = None
    classification: Optional[str] = None
    classification_confidence: Optional[float] = None
    extraction_status: str = "pending"
    extracted_data: Optional[dict[str, Any]] = None
    extraction_confidence: Optional[dict[str, Any]] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    version_number: int = 1
    previous_version_id: Optional[str] = None


class DocumentCreateDTO(BaseModel):
    crew_member_id: Optional[str] = None
    file_name: str = Field(..., min_length=1, max_length=255)
    file_type: str
    file_size: int = Field(..., gt=0)
    storage_type: str = "local"
    storage_path: str
    classification: Optional[str] = None
    uploaded_by: Optional[str] = None


class DocumentConfirmDTO(BaseModel):
    document_id: str
    data: dict[str, Any]


class ExtractionResultDTO(BaseModel):
    document_type: str
    confidence: dict[str, float] = {}
    needs_review: list[str] = []
    document_mismatch: bool = False
    notes: Optional[str] = None


class CrewSearchDTO(BaseModel):
    query: Optional[str] = None
    availability: Optional[str] = None
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


class ReportFilterDTO(BaseModel):
    availability: Optional[str] = None
    project_type: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class LoginDTO(BaseModel):
    email: str
    password: str


class ComplianceStatusDTO(BaseModel):
    crew_id: str
    overall_status: str
    certifications: list[CertificationDTO] = []
    missing_requirements: list[str] = []
    expiring_soon: list[CertificationDTO] = []
    expired: list[CertificationDTO] = []
