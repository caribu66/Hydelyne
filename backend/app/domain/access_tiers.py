"""Data-classification and access-tier policy — single machine-readable source.

This module is the counterpart to ADR 0005 and docs/AUTHORIZATION.md. It owns
the field → classification mapping that every resolver, REST handler, and search
projection must consult. Domain code is framework-free (no imports from api,
auth, graphql, models, services, tasks) so the map can be imported anywhere
without cycle.

Classifications:
- C1 / RECRUITER_SAFE  — low sensitivity, any authenticated user for approved profiles
- C2 / RESTRICTED      — medium, staff (scoped) + admin
- C3 / COMPLIANCE_ONLY — high, admin only (future compliance role may inherit T3)

Tiers map to classifications: T1 allows C1, T2 allows C1+C2, T3 allows C1+C2+C3.
Unmapped fields are deny-by-default (treated as C3).
"""

from __future__ import annotations

from typing import Literal

Classification = Literal["C1", "C2", "C3"]
Tier = Literal["T1", "T2", "T3"]

# Human aliases for readability at call sites.
RECRUITER_SAFE: Classification = "C1"
RESTRICTED: Classification = "C2"
COMPLIANCE_ONLY: Classification = "C3"

# ---------------------------------------------------------------------------
# Field → classification maps
# Keys are model-attribute / GraphQL-field / Meilisearch-field names as they
# appear in CrewMember / Certification / WorkHistory / Document / Project.
# When a GraphQL field aggregates several columns (e.g. passport.*) each
# underlying column is listed explicitly.
# ---------------------------------------------------------------------------

CREW_MEMBER_FIELD_CLASS: dict[str, Classification] = {
    # C1 — recruiter-safe
    "id": "C1",
    "full_name": "C1",
    "nationality": "C1",
    "country_of_residence": "C1",
    "gender": "C1",
    "languages": "C1",
    "flying_point": "C1",
    "availability_status": "C1",
    "availability_date": "C1",
    "profile_completeness_score": "C1",
    "experience_months": "C1",
    "years_of_experience": "C1",
    "education": "C1",
    "professional_summary": "C1",
    "geographical_experience": "C1",
    "systems_experience": "C1",
    "training_qualifications": "C1",
    "tags": "C1",
    "created_at": "C1",
    "updated_at": "C1",
    "publication_status": "C1",
    # role is C1 only for the caller's own record via `me`; enumeration is C3
    "role": "C1",
    # C2 — restricted operational
    "email": "C2",
    "phone": "C2",
    "address": "C2",
    "emergency_contact_name": "C2",
    "emergency_contact_relationship": "C2",
    "emergency_contact_phone": "C2",
    "internal_notes": "C2",
    # C3 — compliance-only
    "date_of_birth": "C3",
    "passport_number": "C3",
    "passport_expiry": "C3",
    "passport_issuing_country": "C3",
    "visa_type": "C3",
    "visa_restrictions": "C3",
    "visa_expiry": "C3",
    "medical_status": "C3",
    "medical_expiry": "C3",
    "medical_provider": "C3",
    "insurance_provider": "C3",
    "insurance_policy_number": "C3",
    "insurance_coverage": "C3",
    "insurance_expiry": "C3",
    "password_hash": "C3",
    "submitted_by": "C3",
}

# GraphQL nested objects map to the same underlying columns; listed for
# resolver-level checks where the field path is e.g. "passport.number".
CREW_MEMBER_NESTED_FIELD_CLASS: dict[str, Classification] = {
    "passport.number": "C3",
    "passport.expiry": "C3",
    "passport.issuing_country": "C3",
    "visa.type": "C3",
    "visa.restrictions": "C3",
    "visa.expiry": "C3",
    "medical.status": "C3",
    "medical.expiry": "C3",
    "medical.provider": "C3",
    "insurance.provider": "C3",
    "insurance.policy_number": "C3",
    "insurance.coverage": "C3",
    "insurance.expiry": "C3",
}

CERTIFICATION_FIELD_CLASS: dict[str, Classification] = {
    "id": "C1",
    "crew_member_id": "C2",
    "cert_type": "C1",
    "status": "C1",
    "verification_status": "C1",
    "issue_date": "C1",
    "expiry_date": "C1",
    # C2 — operational evidence linking
    "cert_number": "C2",
    "issuing_body": "C2",
    "renewal_date": "C2",
    "document_ref": "C2",
    "extracted_confidence": "C2",
    "created_at": "C1",
    "updated_at": "C1",
}

WORK_HISTORY_FIELD_CLASS: dict[str, Classification] = {
    # All work-history rows are operational evidence — C2.
    "id": "C2",
    "crew_member_id": "C2",
    "client_name": "C2",
    "project_name": "C2",
    "project_type": "C2",
    "location": "C2",
    "country": "C2",
    "role": "C2",
    "responsibilities": "C2",
    "start_date": "C2",
    "end_date": "C2",
    "status": "C2",
    "document_ref": "C2",
    "created_at": "C2",
    "updated_at": "C2",
}

DOCUMENT_FIELD_CLASS: dict[str, Classification] = {
    # C2 — metadata safe for ops
    "id": "C2",
    "crew_member_id": "C2",
    "file_name": "C2",
    "file_type": "C2",
    "file_size": "C2",
    "storage_type": "C2",
    "classification": "C2",
    "extraction_status": "C2",
    "uploaded_by": "C2",
    "uploaded_at": "C2",
    "version_number": "C2",
    # C3 — evidence / storage internals
    "extracted_text": "C3",
    "extracted_data": "C3",
    "extraction_confidence": "C3",
    "storage_path": "C3",
    "dropbox_path": "C3",
    "dropbox_revision": "C3",
    "upload_key": "C3",
    "access_log": "C3",
    "classification_confidence": "C3",
    "previous_version_id": "C3",
}

PROJECT_FIELD_CLASS: dict[str, Classification] = {
    "id": "C1",
    "client_name": "C1",
    "project_name": "C1",
    "project_type": "C1",
    "location": "C1",
    "country": "C1",
    "status": "C1",
    "start_date": "C1",
    "end_date": "C1",
    "created_at": "C1",
    "updated_at": "C1",
    # C2 — operational assignment
    "water_depth": "C2",
    "crew_assigned": "C2",
    "requirements": "C2",
    "document_ref": "C2",
}

# Meilisearch general projection must be C1-only. This set is the allow-list
# for the `crew_members` index; any field outside it must not be indexed there.
MEILISEARCH_CREW_C1_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "full_name",
        "nationality",
        "country_of_residence",
        "availability_status",
        "tags",
        "publication_status",
        "gender",
        "languages",
        "flying_point",
        # Derived C1 text fields (stored as text for keyword search)
        "education",
        "geographical_experience",
        "systems_experience",
        "training_qualifications",
        "professional_summary",
    }
)

# Fields that must never appear in the general crew index (C2/C3).
MEILISEARCH_CREW_DENIED_FIELDS: frozenset[str] = frozenset(
    {
        "email",
        "phone",
        "passport_number",
        "passport_expiry",
        "passport_issuing_country",
        "visa_type",
        "visa_restrictions",
        "visa_expiry",
        "medical_status",
        "medical_expiry",
        "medical_provider",
        "insurance_provider",
        "insurance_policy_number",
        "insurance_coverage",
        "insurance_expiry",
        "date_of_birth",
        "address",
        "emergency_contact_name",
        "emergency_contact_phone",
        "extracted_data",
        "extracted_text",
    }
)


def classification_for_crew_field(field: str) -> Classification:
    """Return the classification for a CrewMember field; deny-by-default → C3."""
    if field in CREW_MEMBER_FIELD_CLASS:
        return CREW_MEMBER_FIELD_CLASS[field]
    if field in CREW_MEMBER_NESTED_FIELD_CLASS:
        return CREW_MEMBER_NESTED_FIELD_CLASS[field]
    return "C3"


def is_allowed_for_tier(classification: Classification, tier: Tier) -> bool:
    """Check whether a field of the given classification is readable at a tier."""
    if tier == "T1":
        return classification == "C1"
    if tier == "T2":
        return classification in ("C1", "C2")
    # T3 allows all
    return True


def tier_for_role(role: str) -> Tier:
    """Map an application role to its maximum tier.

    staff is T2 (scoped), admin is T3, any other authenticated role is T1.
    """
    if role == "admin":
        return "T3"
    if role == "staff":
        return "T2"
    return "T1"
