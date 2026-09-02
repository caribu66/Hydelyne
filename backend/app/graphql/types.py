from __future__ import annotations

from enum import Enum
from typing import Optional

import strawberry


@strawberry.type
class PassportInfo:
    number: Optional[str] = None
    expiry: Optional[str] = None
    issuing_country: Optional[str] = None


@strawberry.type
class VisaInfo:
    type: Optional[str] = None
    restrictions: Optional[str] = None
    expiry: Optional[str] = None


@strawberry.type
class MedicalInfo:
    status: Optional[str] = None
    expiry: Optional[str] = None
    provider: Optional[str] = None


@strawberry.type
class InsuranceInfo:
    provider: Optional[str] = None
    policy_number: Optional[str] = None
    coverage: Optional[str] = None
    expiry: Optional[str] = None


@strawberry.type
class Certification:
    id: str
    cert_type: str
    cert_number: Optional[str] = None
    issuing_body: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    renewal_date: Optional[str] = None
    status: str = "pending_verification"
    extracted_confidence: Optional[float] = None
    verification_status: str = "unverified"


@strawberry.type
class WorkHistory:
    id: str
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    project_type: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    role: Optional[str] = None
    responsibilities: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None


@strawberry.type
class DocumentType:
    id: str
    file_name: str
    file_type: str
    file_size: int
    storage_type: str
    classification: Optional[str] = None
    extraction_status: str = "pending"
    extracted_text: Optional[str] = None
    extracted_data: Optional[str] = None
    extraction_confidence: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: str = ""
    version_number: int = 1


@strawberry.type
class CrewMember:
    id: str
    full_name: str
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    languages: Optional[list[str]] = None
    flying_point: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "user"
    passport: Optional[PassportInfo] = None
    visa: Optional[VisaInfo] = None
    medical: Optional[MedicalInfo] = None
    insurance: Optional[InsuranceInfo] = None
    availability_status: str = "available"
    availability_date: Optional[str] = None
    profile_completeness_score: Optional[float] = None
    years_of_experience: Optional[float] = None
    education: Optional[str] = None
    professional_summary: Optional[str] = None
    geographical_experience: Optional[str] = None
    systems_experience: Optional[str] = None
    training_qualifications: Optional[str] = None
    work_history: list[WorkHistory] = strawberry.field(default_factory=list)
    certifications: list[Certification] = strawberry.field(default_factory=list)
    internal_notes: Optional[str] = None
    tags: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@strawberry.type
class Project:
    id: str
    client_name: str
    project_name: str
    project_type: str
    location: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "planning"
    requirements: Optional[str] = None


@strawberry.type
class Report:
    id: str
    report_type: str
    title: str
    generated_at: str
    filters: Optional[str] = None
    summary: str = ""
    data: str = ""
    recommendations: Optional[str] = None


@strawberry.enum
class AvailabilityStatus(Enum):
    AVAILABLE = "available"
    ON_ASSIGNMENT = "on_assignment"
    UNAVAILABLE = "unavailable"


@strawberry.enum
class CertType(Enum):
    BOSIET = "BOSIET"
    STCW = "STCW"
    MMO = "MMO"
    PAM = "PAM"
    NEBOSH = "NEBOSH"
    OFFSHORE_MEDICAL = "OFFSHORE_MEDICAL"
    HSE = "HSE"
    OTHER = "OTHER"


@strawberry.enum
class CertStatus(Enum):
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    PENDING_VERIFICATION = "pending_verification"


@strawberry.enum
class StorageType(Enum):
    LOCAL = "local"
    DROPBOX = "dropbox"


@strawberry.enum
class DocumentClassification(Enum):
    CERT = "cert"
    CV = "cv"
    IDENTITY = "identity"
    PROJECT = "project"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"


@strawberry.enum
class ExtractionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


@strawberry.enum
class ProjectType(Enum):
    MARINE_SEISMIC = "marine_seismic"
    LAND_SEISMIC = "land_seismic"
    OFFSHORE_WIND = "offshore_wind"
    ENVIRONMENTAL = "environmental"
    OTHER = "other"


@strawberry.enum
class ProjectStatus(Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@strawberry.enum
class ReportType(Enum):
    AVAILABILITY = "availability"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    PROJECT_READINESS = "project_readiness"


@strawberry.enum
class VerificationStatus(Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


@strawberry.type
class AuthPayload:
    success: bool
    message: str
    user: Optional[CrewMember] = None
    token: Optional[str] = None


@strawberry.type
class CrewQueryResponse:
    intent: str
    query: str
    summary: str
    results: Optional[str] = None
    criteria: Optional[str] = None
    total_issues: Optional[int] = None
    crew_id: Optional[str] = None
    crew_name: Optional[str] = None


@strawberry.type
class CVExtractionResult:
    document_id: str
    crew_id: str
    status: str
    certifications_created: int
    work_history_created: int
    skills_found: list[str]
    specializations_found: list[str]
