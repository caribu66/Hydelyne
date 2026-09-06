"""Tier-aware redaction for GraphQL return types.

Every CrewMember / Certification / WorkHistory / Document projection must pass
through these helpers before leaving the GraphQL layer. The tier is derived
from the actor's role via `access_tiers.tier_for_role`. C1 is always visible;
C2 requires T2; C3 requires T3. Unmapped fields are deny-by-default (C3).

Frontend defense-in-depth splits queries to avoid requesting C2/C3 for T1, but
backend redaction is the security boundary — a stale cache or forged query
must still see nulls, not values.
"""

from __future__ import annotations

from app.domain.access_tiers import Tier
from app.graphql.types import Certification, CrewMember, DocumentType, Project, WorkHistory


def _tier_allows_c2(tier: Tier) -> bool:
    return tier in ("T2", "T3")


def _tier_allows_c3(tier: Tier) -> bool:
    return tier == "T3"


def scrub_certification(cert: Certification, tier: Tier) -> Certification:
    """Redact C2 fields for T1 callers; C1 fields are always kept."""
    if _tier_allows_c2(tier):
        return cert
    # T1: strip cert_number, issuing_body, renewal_date, document_ref, extracted_confidence (all C2)
    return Certification(
        id=cert.id,
        cert_type=cert.cert_type,
        cert_number=None,
        issuing_body=None,
        issue_date=cert.issue_date,
        expiry_date=cert.expiry_date,
        renewal_date=None,
        status=cert.status,
        document_ref=None,
        extracted_confidence=None,
        verification_status=cert.verification_status,
    )


def scrub_work_history_list(items: list[WorkHistory], tier: Tier) -> list[WorkHistory]:
    """WorkHistory is entirely C2 — T1 sees an empty list."""
    if _tier_allows_c2(tier):
        return items
    return []


def scrub_crew_member(member: CrewMember, tier: Tier) -> CrewMember:
    """Return a tier-scoped copy of a CrewMember GraphQL object."""
    # Always scrub work history and certifications per-tier first
    work_history = scrub_work_history_list(member.work_history, tier)
    certifications = [scrub_certification(c, tier) for c in member.certifications]

    if tier == "T3":
        return CrewMember(
            id=member.id,
            full_name=member.full_name,
            nationality=member.nationality,
            country_of_residence=member.country_of_residence,
            date_of_birth=member.date_of_birth,
            gender=member.gender,
            languages=member.languages,
            flying_point=member.flying_point,
            email=member.email,
            phone=member.phone,
            role=member.role,
            publication_status=member.publication_status,
            passport=member.passport,
            visa=member.visa,
            medical=member.medical,
            insurance=member.insurance,
            availability_status=member.availability_status,
            availability_date=member.availability_date,
            profile_completeness_score=member.profile_completeness_score,
            years_of_experience=member.years_of_experience,
            education=member.education,
            professional_summary=member.professional_summary,
            geographical_experience=member.geographical_experience,
            systems_experience=member.systems_experience,
            training_qualifications=member.training_qualifications,
            work_history=work_history,
            certifications=certifications,
            internal_notes=member.internal_notes,
            tags=member.tags,
            created_at=member.created_at,
            updated_at=member.updated_at,
        )
    if tier == "T2":
        # T2 sees C1+C2, but not C3 (passport/visa/medical/insurance/date_of_birth)
        return CrewMember(
            id=member.id,
            full_name=member.full_name,
            nationality=member.nationality,
            country_of_residence=member.country_of_residence,
            date_of_birth=None,
            gender=member.gender,
            languages=member.languages,
            flying_point=member.flying_point,
            email=member.email,
            phone=member.phone,
            role=member.role,
            publication_status=member.publication_status,
            passport=None,
            visa=None,
            medical=None,
            insurance=None,
            availability_status=member.availability_status,
            availability_date=member.availability_date,
            profile_completeness_score=member.profile_completeness_score,
            years_of_experience=member.years_of_experience,
            education=member.education,
            professional_summary=member.professional_summary,
            geographical_experience=member.geographical_experience,
            systems_experience=member.systems_experience,
            training_qualifications=member.training_qualifications,
            work_history=work_history,
            certifications=certifications,
            internal_notes=member.internal_notes,
            tags=member.tags,
            created_at=member.created_at,
            updated_at=member.updated_at,
        )
    # T1: C1 only
    return CrewMember(
        id=member.id,
        full_name=member.full_name,
        nationality=member.nationality,
        country_of_residence=member.country_of_residence,
        date_of_birth=None,
        gender=member.gender,
        languages=member.languages,
        flying_point=member.flying_point,
        email=None,
        phone=None,
        role=member.role,
        publication_status=member.publication_status,
        passport=None,
        visa=None,
        medical=None,
        insurance=None,
        availability_status=member.availability_status,
        availability_date=member.availability_date,
        profile_completeness_score=member.profile_completeness_score,
        years_of_experience=member.years_of_experience,
        education=member.education,
        professional_summary=member.professional_summary,
        geographical_experience=member.geographical_experience,
        systems_experience=member.systems_experience,
        training_qualifications=member.training_qualifications,
        work_history=[],
        certifications=certifications,
        internal_notes=None,
        tags=member.tags,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def scrub_document(doc: DocumentType, tier: Tier) -> DocumentType:
    """Scrub DocumentType per tier.

    T1: not allowed to see documents at all — caller should handle None/[].
         This helper is not used for T1; resolvers return None/[] instead.
    T2: metadata only (C2), no extractedText/extractedData/extractionConfidence (C3).
    T3: full.
    """
    if tier == "T3":
        return doc
    # T2: strip C3 evidence
    return DocumentType(
        id=doc.id,
        file_name=doc.file_name,
        file_type=doc.file_type,
        file_size=doc.file_size,
        storage_type=doc.storage_type,
        classification=doc.classification,
        extraction_status=doc.extraction_status,
        extracted_text=None,
        extracted_data=None,
        extraction_confidence=None,
        uploaded_by=doc.uploaded_by,
        uploaded_at=doc.uploaded_at,
        version_number=doc.version_number,
    )


def scrub_project(project: Project, tier: Tier) -> Project:
    """Project: C1 always, C2 (requirements/crewAssigned) only for T2/T3."""
    if _tier_allows_c2(tier):
        return project
    return Project(
        id=project.id,
        client_name=project.client_name,
        project_name=project.project_name,
        project_type=project.project_type,
        location=project.location,
        country=project.country,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        requirements=None,
    )
