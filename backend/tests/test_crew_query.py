"""Regression tests for resilient natural-language crew search."""
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.models import Certification, CrewMember, WorkHistory
from app.services.crew_query import CrewQueryService


def test_medical_query_rule_is_a_candidate_search():
    result = CrewQueryService._apply_deterministic_query_rules(
        "Who has medical experience?",
        {"intent": "general", "entities": {}},
    )

    assert result["intent"] == "search"
    assert result["entities"]["medical_required"] is True
    assert "OGUK Medical" in result["entities"]["certifications"]


def test_multi_criteria_query_extracts_nationality_medical_and_imca_family():
    result = CrewQueryService._apply_deterministic_query_rules(
        "Find Spanish crew with a current medical and IMCA certification",
        {"intent": "search", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Spanish"
    assert result["entities"]["medical_required"] is True
    assert result["entities"]["medical_valid"] is True
    assert result["entities"]["certification_keywords"] == ["IMCA"]


def test_experience_query_extracts_a_minimum_years_requirement():
    result = CrewQueryService._apply_deterministic_query_rules(
        "Find Spanish crew with 3 years of experience and a medical certificate",
        {"intent": "search", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Spanish"
    assert result["entities"]["min_experience_years"] == 3.0


def test_polish_pam_mmo_query_keeps_nationality_and_skill_constraints():
    result = CrewQueryService._apply_deterministic_query_rules(
        "PAM MMO Poland show me the top contractor",
        {"intent": "matching", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Polish"
    assert {"pam", "mmo"}.issubset({skill.lower() for skill in result["entities"]["skills"]})


def test_controlled_typo_correction_is_visible_and_searchable():
    result = CrewQueryService._apply_deterministic_query_rules(
        "Find Spanih crew with a medicl and IMCA servey QC experience",
        {"intent": "search", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Spanish"
    assert result["entities"]["medical_required"] is True
    assert result["entities"]["certification_keywords"] == ["IMCA"]
    assert {item["to"] for item in result["entities"]["corrections"]} >= {
        "spanish", "medical", "survey"
    }


@pytest.mark.asyncio
async def test_medical_query_finds_dedicated_medical_records(db_session):
    crew = CrewMember(
        full_name="Dr Maya Patel",
        email="maya.patel@example.com",
        medical_status="fit",
        medical_expiry=date(2027, 1, 1),
    )
    db_session.add(crew)
    await db_session.commit()

    service = CrewQueryService()
    service._generate_response = AsyncMock(return_value="Medical-ready candidates found.")
    result = await service._handle_search(
        "Who has medical experience?",
        {"medical_required": True, "certifications": ["OGUK Medical"]},
        db_session,
    )

    assert {candidate["id"] for candidate in result["results"]} >= {crew.id}


@pytest.mark.asyncio
async def test_candidate_search_matrix(db_session):
    """Exercise the entity shapes the AI produces for common search prompts."""
    medic = CrewMember(
        full_name="Search Matrix Medical", email="matrix-medical@example.com",
        medical_status="fit", availability_status="available",
    )
    surveyor = CrewMember(
        full_name="Search Matrix Survey", email="matrix-survey@example.com",
        availability_status="available",
    )
    unavailable = CrewMember(
        full_name="Search Matrix Unavailable", email="matrix-unavailable@example.com",
        availability_status="unavailable",
    )
    db_session.add_all([medic, surveyor, unavailable])
    await db_session.flush()
    db_session.add(Certification(crew_member_id=surveyor.id, cert_type="BOSIET"))
    db_session.add(WorkHistory(
        crew_member_id=surveyor.id,
        project_type="Offshore wind survey",
        location="Aberdeen, Scotland",
        responsibilities="Offshore hydrographic survey operations",
    ))
    await db_session.commit()

    service = CrewQueryService()
    service._generate_response = AsyncMock(return_value="Candidates found.")
    searches = [
        ("Who has medical experience?", {"medical_required": True, "certifications": ["OGUK Medical"]}, medic.id),
        ("Find crew with BOSIET certification", {"certifications": ["BOSIET"]}, surveyor.id),
        ("Who has offshore wind experience?", {"project_type": "offshore"}, surveyor.id),
        ("Show specialists in Aberdeen", {"location": "Aberdeen"}, surveyor.id),
        ("Find available crew with a medical", {"medical_required": True, "availability": "available"}, medic.id),
        ("List unavailable specialists", {"availability": "unavailable"}, unavailable.id),
    ]

    for query, entities, expected_id in searches:
        result = await service._handle_search(query, entities, db_session)
        assert expected_id in {candidate["id"] for candidate in result["results"]}, query
