"""Deterministic natural-language crew-query interpretation.

Pure vocabulary and rule logic extracted from ``app/services/crew_query.py``
(that file was 846 lines; this covers the one self-contained, framework-free
piece of it — see ``docs/CHANGELOG.md`` for the extraction). This module
must stay free of database, LLM-client, and transport dependencies: it only
ever turns a query string plus an already-classified intent dict into a
richer entities dict, deterministically.
"""

from __future__ import annotations

import re
from difflib import get_close_matches
from typing import Any

from app.domain.certifications import CERT_ALIASES, CERT_FAMILIES

NATIONALITY_ALIASES = {
    "british": "British",
    "dutch": "Dutch",
    "norwegian": "Norwegian",
    "french": "French",
    "canadian": "Canadian",
    "german": "German",
    "danish": "Danish",
    "swedish": "Swedish",
    "australian": "Australian",
    "american": "American",
    "irish": "Irish",
    "belgian": "Belgian",
    "spanish": "Spanish",
    "poland": "Polish",
    "polish": "Polish",
    "italian": "Italian",
    "new zealander": "New Zealander",
    "singaporean": "Singaporean",
    "maltese": "Maltese",
    "greek": "Greek",
    "finnish": "Finnic",
    "icelandic": "Icelandic",
}

# Intentionally limited to controlled recruitment vocabulary. This avoids an
# unsafe "best guess" correction of a person's name or a compliance document.
TYPO_VOCABULARY = {
    "spanish",
    "medical",
    "medicals",
    "bosiet",
    "stcw",
    "imca",
    "iogp",
    "opito",
    "hydrography",
    "hydrographer",
    "hydrographic",
    "seismic",
    "geotechnical",
    "offshore",
    "available",
    "unavailable",
    "aberdeen",
    "survey",
    "wind",
    "uxo",
    "pamguard",
    "nebosh",
    "geotech",
    "multibeam",
    "environmental",
}


def normalize_search_typos(query: str) -> tuple[str, list[dict[str, str]]]:
    """Correct close matches from the controlled search vocabulary only."""
    corrections: list[dict[str, str]] = []

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(0)
        lower_token = token.lower()
        if len(lower_token) < 4 or lower_token in TYPO_VOCABULARY:
            return token
        suggestion = get_close_matches(lower_token, TYPO_VOCABULARY, n=1, cutoff=0.78)
        if not suggestion:
            return token
        corrected = suggestion[0]
        corrections.append({"from": token, "to": corrected})
        return corrected

    return re.sub(r"[A-Za-z]+", replace_token, query), corrections


def apply_deterministic_query_rules(query: str, classified: dict[str, Any]) -> dict[str, Any]:
    """Add unambiguous crew-domain meaning that must not depend on an LLM."""
    normalized = dict(classified)
    entities = dict(normalized.get("entities") or {})
    corrected_query, corrections = normalize_search_typos(query)
    lower_query = corrected_query.lower()
    if corrections:
        entities["corrections"] = corrections
    has_medical_term = any(
        term in lower_query
        for term in (
            "medical",
            "medicals",
            "medical fitness",
            "medical clearance",
            "fit to work",
        )
    )
    is_medical_compliance_query = has_medical_term and any(
        term in lower_query
        for term in (
            "expired",
            "expiring",
            "renew",
            "renewal",
            "non-compliant",
        )
    )

    if has_medical_term and not is_medical_compliance_query:
        normalized["intent"] = "search"
        entities["medical_required"] = True
        certifications = list(entities.get("certifications") or [])
        if not any("medical" in str(certification).lower() for certification in certifications):
            certifications.append("OGUK Medical")
        entities["certifications"] = certifications

        if any(
            term in lower_query
            for term in (
                "current medical",
                "valid medical",
                "in-date medical",
                "in date medical",
                "up to date medical",
                "medical ready",
            )
        ):
            entities["medical_valid"] = True

    for alias, nationality in NATIONALITY_ALIASES.items():
        if alias in lower_query:
            entities["nationality"] = nationality
            break

    certification_keywords = list(entities.get("certification_keywords") or [])
    for keyword, family in CERT_FAMILIES.items():
        if keyword in lower_query and family not in certification_keywords:
            certification_keywords.append(family)
    if certification_keywords:
        entities["certification_keywords"] = certification_keywords

    # Retain useful matching even if the language model is offline. These
    # terms match tags, work history, responsibilities and credentials.
    detected_terms = list(entities.get("skills") or [])
    for term in (
        "offshore",
        "hydrograph",
        "seismic",
        "geotechnical",
        "uxo",
        "wind",
        "environmental",
        "pamguard",
        "multibeam",
        "pam",
        "mmo",
    ):
        if term in lower_query and term not in detected_terms:
            detected_terms.append(term)
    if detected_terms:
        entities["skills"] = detected_terms

    if "aberdeen" in lower_query and not entities.get("location"):
        entities["location"] = "Aberdeen"
    if (
        "available" in lower_query
        and "unavailable" not in lower_query
        and not entities.get("availability")
    ):
        entities["availability"] = "available"
    elif "unavailable" in lower_query and not entities.get("availability"):
        entities["availability"] = "unavailable"

    inferred_certifications = list(entities.get("certifications") or [])
    for alias, certificate in CERT_ALIASES.items():
        if " " not in alias and alias in lower_query and certificate not in inferred_certifications:
            inferred_certifications.append(certificate)
    if inferred_certifications:
        entities["certifications"] = inferred_certifications

    experience_match = re.search(
        r"\b(?:at least |minimum of |over )?(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?)\s+(?:of\s+)?experience\b",
        lower_query,
    )
    if experience_match:
        years = float(experience_match.group(1))
        entities["min_experience_years"] = years
        if "exactly" in lower_query or "only" in lower_query:
            entities["max_experience_years"] = years

    normalized["entities"] = entities
    return normalized
