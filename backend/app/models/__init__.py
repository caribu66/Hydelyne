import uuid
from datetime import date, datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import JSON, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CrewMember(Base):
    __tablename__ = "crew_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(100))
    country_of_residence: Mapped[Optional[str]] = mapped_column(String(100))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    gender: Mapped[Optional[str]] = mapped_column(String(50))
    languages: Mapped[Optional[list]] = mapped_column(JSON)
    flying_point: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)
    # Existing rows remain approved. New CV-led submissions explicitly use
    # draft/pending_review until an administrator confirms the extraction.
    publication_status: Mapped[str] = mapped_column(
        String(20), default="approved", server_default="approved", index=True
    )
    submitted_by: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    address: Mapped[Optional[str]] = mapped_column(Text)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    emergency_contact_relationship: Mapped[Optional[str]] = mapped_column(String(100))
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    passport_number: Mapped[Optional[str]] = mapped_column(String(50))
    passport_expiry: Mapped[Optional[date]] = mapped_column(Date)
    passport_issuing_country: Mapped[Optional[str]] = mapped_column(String(100))
    visa_type: Mapped[Optional[str]] = mapped_column(String(100))
    visa_restrictions: Mapped[Optional[str]] = mapped_column(Text)
    visa_expiry: Mapped[Optional[date]] = mapped_column(Date)
    medical_status: Mapped[Optional[str]] = mapped_column(String(50))
    medical_expiry: Mapped[Optional[date]] = mapped_column(Date)
    medical_provider: Mapped[Optional[str]] = mapped_column(String(255))
    insurance_provider: Mapped[Optional[str]] = mapped_column(String(255))
    insurance_policy_number: Mapped[Optional[str]] = mapped_column(String(100))
    insurance_coverage: Mapped[Optional[str]] = mapped_column(Text)
    insurance_expiry: Mapped[Optional[date]] = mapped_column(Date)
    availability_status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    availability_date: Mapped[Optional[date]] = mapped_column(Date)
    profile_completeness_score: Mapped[Optional[float]] = mapped_column(Float)
    # Audited aggregate of non-overlapping work-history periods. Keep months
    # rather than rounded years so candidate filters remain precise.
    experience_months: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    education: Mapped[Optional[str]] = mapped_column(Text)
    # Captured verbatim from the CV's PROFESSIONAL SUMMARY section by the
    # deterministic extractor — free text, never AI-interpreted at ingestion.
    professional_summary: Mapped[Optional[str]] = mapped_column(Text)
    # Countries and locations evidenced by source-linked work history.
    geographical_experience: Mapped[Optional[list]] = mapped_column(JSON)
    systems_experience: Mapped[Optional[list]] = mapped_column(JSON)
    training_qualifications: Mapped[Optional[list]] = mapped_column(JSON)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[Optional[list]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )

    certifications = relationship(
        "Certification", back_populates="crew_member", cascade="all, delete-orphan"
    )
    work_history = relationship(
        "WorkHistory", back_populates="crew_member", cascade="all, delete-orphan"
    )
    documents = relationship("Document", back_populates="crew_member")
    assignments = relationship(
        "CampaignAssignment", back_populates="crew_member", cascade="all, delete-orphan"
    )


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crew_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crew_members.id"), index=True
    )
    cert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    cert_number: Mapped[Optional[str]] = mapped_column(String(100))
    issuing_body: Mapped[Optional[str]] = mapped_column(String(255))
    issue_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    renewal_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending_verification", index=True)
    document_ref: Mapped[Optional[str]] = mapped_column(String(255))
    extracted_confidence: Mapped[Optional[float]] = mapped_column(Float)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )

    crew_member = relationship("CrewMember", back_populates="certifications")


class WorkHistory(Base):
    __tablename__ = "work_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crew_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crew_members.id"), index=True
    )
    client_name: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(255))
    project_type: Mapped[Optional[str]] = mapped_column(String(255))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    country: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    role: Mapped[Optional[str]] = mapped_column(String(255))
    responsibilities: Mapped[Optional[str]] = mapped_column(Text)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(String(20))
    document_ref: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )

    crew_member = relationship("CrewMember", back_populates="work_history")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str] = mapped_column(String(50), index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    water_depth: Mapped[Optional[str]] = mapped_column(String(50))
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="planning", index=True)
    crew_assigned: Mapped[Optional[list]] = mapped_column(JSON)
    requirements: Mapped[Optional[dict]] = mapped_column(JSON)
    document_ref: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )

    assignments = relationship("CampaignAssignment", back_populates="project")


class Vessel(Base):
    __tablename__ = "vessels"

    imo: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    mmsi: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    callsign: Mapped[Optional[str]] = mapped_column(String(50))
    vessel_type: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    flag: Mapped[Optional[str]] = mapped_column(String(50))
    length: Mapped[Optional[float]] = mapped_column(Float)
    width: Mapped[Optional[float]] = mapped_column(Float)
    year_built: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )

    assignments = relationship("CampaignAssignment", back_populates="vessel")


class CampaignAssignment(Base):
    __tablename__ = "campaign_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crew_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crew_members.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    vessel_imo: Mapped[str] = mapped_column(
        String(20), ForeignKey("vessels.imo", ondelete="RESTRICT"), index=True
    )
    role_on_board: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="proposed", server_default="proposed", index=True
    )
    agreed_day_rate: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )

    crew_member = relationship("CrewMember", back_populates="assignments")
    project = relationship("Project", back_populates="assignments")
    vessel = relationship("Vessel", back_populates="assignments")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crew_member_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("crew_members.id"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_type: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    dropbox_path: Mapped[Optional[str]] = mapped_column(String(500))
    dropbox_revision: Mapped[Optional[str]] = mapped_column(String(100))
    classification: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    classification_confidence: Mapped[Optional[float]] = mapped_column(Float)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # Complete text recovered from the original document. The source PDF in
    # Dropbox remains authoritative; this supports search and audit without
    # flattening every CV detail into the crew profile.
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSON)
    extraction_confidence: Mapped[Optional[dict]] = mapped_column(JSON)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(255))
    upload_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    previous_version_id: Mapped[Optional[str]] = mapped_column(String(36))
    access_log: Mapped[Optional[list]] = mapped_column(JSON)

    crew_member = relationship("CrewMember", back_populates="documents")


class DocumentRequest(Base):
    """A time-limited, bearer-token upload request sent to a contractor."""

    __tablename__ = "document_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crew_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crew_members.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    expires_at: Mapped[datetime] = mapped_column(index=True)
    created_by: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    revoked_at: Mapped[Optional[datetime]] = mapped_column()


class IncomingDocumentReview(Base):
    """Durable staff queue item for a contractor-uploaded document."""

    __tablename__ = "incoming_document_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_requests.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="unread", server_default="unread", index=True
    )
    claimed_by: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column()
    resolved_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now(), index=True)


class CVReview(Base):
    """Durable review state for one deterministic CV extraction."""

    __tablename__ = "cv_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True
    )
    crew_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crew_members.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(24), default="processing", server_default="processing", index=True
    )
    prior_publication_status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft"
    )
    proposed_data: Mapped[Optional[dict]] = mapped_column(JSON)
    approved_data: Mapped[Optional[dict]] = mapped_column(JSON)
    submitted_by: Mapped[str] = mapped_column(String(36), index=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column()


class ProfileAccessEvent(Base):
    """Privacy-safe audit metadata for specialist-profile reads."""

    __tablename__ = "profile_access_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    crew_member_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now(), index=True)
