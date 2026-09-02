"""Shared field-value vocabulary for CrewMember/Certification status fields.

These values are duplicated today as magic strings in several places
(``crew_query.py``'s filter branches, ``document_tasks.py``'s expiry check,
the ``AvailabilityStatus``/``CertStatus`` GraphQL enums in
``app/graphql/types.py``). This module gives the Python-level (non-GraphQL)
call sites one place to import the canonical values from, instead of each
retyping the same literals.

Note: the GraphQL-facing enums in ``app/graphql/types.py`` are a separate,
existing source of truth for the API surface and are not replaced here —
keeping them in sync with this module is a manual step until a future pass
unifies them.
"""

from __future__ import annotations

AVAILABILITY_STATUS_VALUES: tuple[str, ...] = ("available", "on_assignment", "unavailable")

CERT_STATUS_VALUES: tuple[str, ...] = ("pending_verification", "valid", "expiring_soon", "expired")

CERT_VERIFICATION_STATUS_VALUES: tuple[str, ...] = ("unverified", "verified", "rejected")

DOCUMENT_CLASSIFICATIONS: tuple[str, ...] = (
    "certificate",
    "cv",
    "identity",
    "project",
    "performance",
    "compliance",
    "other",
)
