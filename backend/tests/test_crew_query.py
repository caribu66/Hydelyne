"""Regression tests for resilient natural-language crew search."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.domain.crew_query_rules import apply_deterministic_query_rules
from app.models import Certification, CrewMember, WorkHistory
from app.services.crew_query import CrewQueryService, _validate_llm_response


def test_medical_query_rule_is_a_candidate_search():
    result = apply_deterministic_query_rules(
        "Who has medical experience?",
        {"intent": "general", "entities": {}},
    )

    assert result["intent"] == "search"
    assert result["entities"]["medical_required"] is True
    assert "OGUK Medical" in result["entities"]["certifications"]


def test_multi_criteria_query_extracts_nationality_medical_and_imca_family():
    result = apply_deterministic_query_rules(
        "Find Spanish crew with a current medical and IMCA certification",
        {"intent": "search", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Spanish"
    assert result["entities"]["medical_required"] is True
    assert result["entities"]["medical_valid"] is True
    assert result["entities"]["certification_keywords"] == ["IMCA"]


def test_experience_query_extracts_a_minimum_years_requirement():
    result = apply_deterministic_query_rules(
        "Find Spanish crew with 3 years of experience and a medical certificate",
        {"intent": "search", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Spanish"
    assert result["entities"]["min_experience_years"] == 3.0


def test_common_natural_search_phrases_have_offline_rules():
    north_sea = apply_deterministic_query_rules(
        "Who has worked in the North Sea?", {"intent": "search", "entities": {}}
    )
    next_month = apply_deterministic_query_rules(
        "Show surveyors available next month.", {"intent": "search", "entities": {}}
    )
    medic = apply_deterministic_query_rules(
        "Find offshore medics with valid BOSIET.", {"intent": "search", "entities": {}}
    )

    assert north_sea["entities"]["location"] == "North Sea"
    assert next_month["entities"]["availability"] == "available"
    assert date.fromisoformat(next_month["entities"]["availability_by"]) > date.today()
    assert "medic" in medic["entities"]["skills"]
    assert medic["entities"]["certifications"] == ["BOSIET"]
    assert medic["entities"]["certifications_valid"] is True


def test_polish_pam_mmo_query_keeps_nationality_and_skill_constraints():
    result = apply_deterministic_query_rules(
        "PAM MMO Poland show me the top contractor",
        {"intent": "matching", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Polish"
    assert {"pam", "mmo"}.issubset({skill.lower() for skill in result["entities"]["skills"]})


def test_controlled_typo_correction_is_visible_and_searchable():
    result = apply_deterministic_query_rules(
        "Find Spanih crew with a medicl and IMCA servey QC experience",
        {"intent": "search", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Spanish"
    assert result["entities"]["medical_required"] is True
    assert result["entities"]["certification_keywords"] == ["IMCA"]
    assert {item["to"] for item in result["entities"]["corrections"]} >= {
        "spanish",
        "medical",
        "survey",
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
        full_name="Search Matrix Medical",
        email="matrix-medical@example.com",
        medical_status="fit",
        availability_status="available",
    )
    surveyor = CrewMember(
        full_name="Search Matrix Survey",
        email="matrix-survey@example.com",
        availability_status="available",
    )
    unavailable = CrewMember(
        full_name="Search Matrix Unavailable",
        email="matrix-unavailable@example.com",
        availability_status="unavailable",
    )
    db_session.add_all([medic, surveyor, unavailable])
    await db_session.flush()
    db_session.add(Certification(crew_member_id=surveyor.id, cert_type="BOSIET"))
    db_session.add(
        WorkHistory(
            crew_member_id=surveyor.id,
            project_type="Offshore wind survey",
            location="Aberdeen, Scotland",
            responsibilities="Offshore hydrographic survey operations",
        )
    )
    await db_session.commit()

    service = CrewQueryService()
    service._generate_response = AsyncMock(return_value="Candidates found.")
    searches = [
        (
            "Who has medical experience?",
            {"medical_required": True, "certifications": ["OGUK Medical"]},
            medic.id,
        ),
        ("Find crew with BOSIET certification", {"certifications": ["BOSIET"]}, surveyor.id),
        ("Who has offshore wind experience?", {"project_type": "offshore"}, surveyor.id),
        ("Show specialists in Aberdeen", {"location": "Aberdeen"}, surveyor.id),
        (
            "Find available crew with a medical",
            {"medical_required": True, "availability": "available"},
            medic.id,
        ),
        ("List unavailable specialists", {"availability": "unavailable"}, unavailable.id),
    ]

    for query, entities, expected_id in searches:
        result = await service._handle_search(query, entities, db_session)
        assert expected_id in {candidate["id"] for candidate in result["results"]}, query


@pytest.mark.asyncio
async def test_valid_certificate_and_availability_date_are_enforced(db_session):
    eligible = CrewMember(
        full_name="Eligible Medic",
        availability_status="available",
        availability_date=date.today() + timedelta(days=10),
        tags=["offshore medic"],
    )
    expired = CrewMember(
        full_name="Expired Medic",
        availability_status="available",
        availability_date=date.today() + timedelta(days=10),
        tags=["offshore medic"],
    )
    db_session.add_all([eligible, expired])
    await db_session.flush()
    db_session.add_all(
        [
            Certification(
                crew_member_id=eligible.id,
                cert_type="BOSIET",
                expiry_date=date.today() + timedelta(days=120),
            ),
            Certification(
                crew_member_id=expired.id,
                cert_type="BOSIET",
                expiry_date=date.today() - timedelta(days=1),
            ),
        ]
    )
    await db_session.commit()

    service = CrewQueryService()
    result = await service._handle_search(
        "Find offshore medics with valid BOSIET",
        apply_deterministic_query_rules(
            "Find offshore medics with valid BOSIET", {"intent": "search", "entities": {}}
        )["entities"],
        db_session,
    )

    assert [candidate["id"] for candidate in result["results"]] == [eligible.id]


@pytest.mark.asyncio
async def test_search_falls_back_when_local_ai_service_is_unavailable(db_session, monkeypatch):
    """Search remains deterministic and publication-safe during Ollama downtime."""
    approved = CrewMember(
        full_name="Offline Search Medic",
        publication_status="approved",
        tags=["offshore medic"],
    )
    draft = CrewMember(
        full_name="Offline Hidden Medic",
        publication_status="draft",
        submitted_by="staff-1",
        tags=["offshore medic"],
    )
    db_session.add_all([approved, draft])
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.crew_query.ollama_client.extract",
        AsyncMock(side_effect=RuntimeError("local AI unavailable")),
    )

    result = await CrewQueryService().process_query("Find offshore medics", db_session)

    assert [candidate["id"] for candidate in result["results"]] == [approved.id]
    assert result["criteria"]["skills"] == ["offshore", "medic"]


def test_current_offshore_medical_query_rule():
    result = apply_deterministic_query_rules(
        "Who has a current offshore medical?",
        {"intent": "general", "entities": {}},
    )

    assert result["intent"] == "search"
    assert result["entities"]["medical_required"] is True
    assert result["entities"]["medical_valid"] is True
    assert "OGUK Medical" in result["entities"]["certifications"]
    assert "skills" not in result["entities"] or "offshore" not in result["entities"]["skills"]


def test_validate_llm_response_accepts_valid_payload():
    raw = {
        "intent": "search",
        "entities": {
            "certifications": ["BOSIET"],
            "skills": ["offshore"],
            "nationality": "Spanish",
            "min_experience_years": 3.0,
            "medical_required": True,
            "medical_valid": False,
            "availability": "available immediately",
        },
        "confidence": 0.95,
    }
    validated = _validate_llm_response(raw)

    assert validated["intent"] == "search"
    assert validated["entities"]["certifications"] == ["BOSIET"]
    assert validated["entities"]["nationality"] == "Spanish"
    assert validated["entities"]["min_experience_years"] == 3.0
    assert validated["entities"]["medical_required"] is True
    assert validated["entities"]["medical_valid"] is False
    assert validated["confidence"] == 0.95


def test_validate_llm_response_rejects_malformed_types():
    raw = {
        "intent": "search",
        "entities": {
            "certifications": "BOSIET",
            "skills": "offshore",
            "nationality": 123,
            "min_experience_years": "three",
            "medical_required": "yes",
            "availability": "maybe",
        },
        "confidence": 2.0,
    }
    validated = _validate_llm_response(raw)

    assert validated["intent"] == "search"
    assert validated["entities"].get("certifications") is None
    assert validated["entities"].get("skills") is None
    assert validated["entities"].get("nationality") is None
    assert validated["entities"].get("min_experience_years") is None
    assert validated["entities"].get("medical_required") is None
    assert validated["entities"].get("availability") is None
    assert validated["confidence"] is None


def test_validate_llm_response_falls_back_to_general_on_invalid_intent():
    raw = {"intent": "unknown_intent", "entities": {}}
    validated = _validate_llm_response(raw)

    assert validated["intent"] == "general"


def test_validate_llm_response_handles_non_dict_input():
    with pytest.raises(ValueError, match="non-object response"):
        _validate_llm_response("not a dict")  # type: ignore[arg-type]


def test_validate_llm_response_drops_out_of_range_availability():
    raw = {
        "intent": "search",
        "entities": {"availability": "maybe"},
    }
    validated = _validate_llm_response(raw)

    assert "availability" not in validated["entities"]
