"""Regression tests for resilient natural-language crew search."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update

from app.domain.crew_query_rules import MAX_SEARCH_QUERY_LENGTH, apply_deterministic_query_rules
from app.models import Certification, CrewMember, WorkHistory
from app.services.crew import crew_service
from app.services.crew_query import (
    CrewQueryService,
    _contains_like,
    _derived_compliance_status,
    _experience_years,
    _validate_llm_response,
)


def test_query_text_is_literal_when_used_in_sql_like_patterns():
    assert _contains_like(r"100%_ready\now") == r"%100\%\_ready\\now%"


def test_experience_years_preserves_unknown_values():
    assert _experience_years(None) is None
    assert _experience_years(150) == 12.5


@pytest.mark.asyncio
async def test_generated_prose_is_bounded(monkeypatch):
    from app.services.crew_query import MAX_GENERATED_RESPONSE_LENGTH

    monkeypatch.setattr(
        "app.services.crew_query.ollama_client.extract",
        AsyncMock(return_value={"response": "x" * (MAX_GENERATED_RESPONSE_LENGTH + 1_000)}),
    )

    result = await CrewQueryService()._generate_response(
        "summarize_response",
        "summarize this profile",
        "{}",
        prose=True,
        document_data="none",
    )

    assert len(result) == MAX_GENERATED_RESPONSE_LENGTH


@pytest.mark.asyncio
async def test_oversized_intent_response_uses_deterministic_fallback(monkeypatch):
    from app.services.crew_query import MAX_INTENT_RESPONSE_LENGTH

    monkeypatch.setattr(
        "app.services.crew_query.ollama_client.extract",
        AsyncMock(return_value={"response": "{" + "x" * MAX_INTENT_RESPONSE_LENGTH + "}"}),
    )

    result = await CrewQueryService()._classify_intent("find available surveyors")

    assert result["intent"] == "search"
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["   ", "x" * (MAX_SEARCH_QUERY_LENGTH + 1)])
async def test_natural_search_rejects_blank_or_oversized_query(query):
    with pytest.raises(ValueError, match="Search query"):
        await CrewQueryService().process_query(query, AsyncMock())


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["   ", "x" * (MAX_SEARCH_QUERY_LENGTH + 1)])
async def test_keyword_search_rejects_blank_or_oversized_query(query):
    with pytest.raises(ValueError, match="Search query"):
        await crew_service.list_crew_members(search=query)


def test_medical_query_rule_is_a_candidate_search():
    result = apply_deterministic_query_rules(
        "Who has medical experience?",
        {"intent": "general", "entities": {}},
    )

    assert result["intent"] == "search"
    assert result["entities"]["medical_required"] is True
    assert "OGUK Medical" in result["entities"]["certifications"]


def test_explicit_compliance_language_cannot_be_downgraded_to_profile_search():
    result = apply_deterministic_query_rules(
        "Find crew with expired medicals",
        {"intent": "search", "entities": {"medical_required": True}},
    )

    assert result["intent"] == "compliance"


def test_multi_criteria_query_extracts_nationality_medical_and_imca_family():
    result = apply_deterministic_query_rules(
        "Find Spanish crew with a current medical and IMCA certification",
        {"intent": "search", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Spanish"
    assert result["entities"]["medical_required"] is True
    assert result["entities"]["medical_valid"] is True
    assert result["entities"]["certification_keywords"] == ["IMCA"]


def test_finnish_nationality_uses_canonical_stored_value():
    result = apply_deterministic_query_rules(
        "Find Finnish hydrographers",
        {"intent": "search", "entities": {}},
    )

    assert result["entities"]["nationality"] == "Finnish"


def test_environmental_skill_does_not_imply_mmo_certification():
    result = apply_deterministic_query_rules(
        "Find environmental specialists",
        {"intent": "search", "entities": {}},
    )

    assert "environmental" in result["entities"]["skills"]
    assert "JNCC MMO" not in result["entities"].get("certifications", [])


def test_certification_aliases_require_word_boundaries():
    false_positive = apply_deterministic_query_rules(
        "Find these approved specialists", {"intent": "search", "entities": {}}
    )
    real_terms = apply_deterministic_query_rules(
        "Find ROV specialists with HSE certification",
        {"intent": "search", "entities": {}},
    )

    assert false_positive["entities"].get("certifications", []) == []
    assert {"ROV Video Verification", "HSE Advisory"}.issubset(
        real_terms["entities"]["certifications"]
    )


def test_nationality_aliases_require_word_boundaries():
    result = apply_deterministic_query_rules(
        "Find polished surveyors", {"intent": "search", "entities": {}}
    )

    assert "nationality" not in result["entities"]


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


def test_unavailable_next_month_does_not_get_available_date_constraint():
    result = apply_deterministic_query_rules(
        "Show unavailable specialists next month.", {"intent": "search", "entities": {}}
    )

    assert result["entities"]["availability"] == "unavailable"
    assert "availability_by" not in result["entities"]


@pytest.mark.parametrize(
    "query", ["Show contractors not available", "Find no longer available crew"]
)
def test_negative_available_language_maps_to_unavailable(query):
    result = apply_deterministic_query_rules(query, {"intent": "search", "entities": {}})

    assert result["entities"]["availability"] == "unavailable"


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
    await db_session.flush()
    db_session.add(Certification(crew_member_id=crew.id, cert_type="OGUK Medical"))
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
async def test_certificate_search_keeps_legacy_null_lifecycle_values(db_session):
    crew = CrewMember(full_name="Legacy Certificate Profile", publication_status="approved")
    db_session.add(crew)
    await db_session.flush()
    certificate = Certification(
        crew_member_id=crew.id,
        cert_type="BOSIET",
        status="pending_verification",
        verification_status="unverified",
    )
    db_session.add(certificate)
    await db_session.commit()
    await db_session.execute(
        update(Certification)
        .where(Certification.id == certificate.id)
        .values(status=None, verification_status=None)
    )
    await db_session.commit()

    result = await CrewQueryService()._handle_search(
        "Find crew with BOSIET certification",
        {"certifications": ["BOSIET"]},
        db_session,
    )

    assert crew.id in {candidate["id"] for candidate in result["results"]}


@pytest.mark.asyncio
async def test_valid_search_excludes_certificates_awaiting_verification(db_session):
    pending = CrewMember(full_name="Pending Medical Evidence", publication_status="approved")
    valid = CrewMember(full_name="Verified Medical Evidence", publication_status="approved")
    expiring = CrewMember(
        full_name="Expiring Verified Medical Evidence", publication_status="approved"
    )
    missing_expiry = CrewMember(
        full_name="Verified Medical Without Expiry", publication_status="approved"
    )
    unverified_valid = CrewMember(
        full_name="Unverified Valid Medical Evidence", publication_status="approved"
    )
    db_session.add_all([pending, valid, expiring, missing_expiry, unverified_valid])
    await db_session.flush()
    db_session.add_all(
        [
            Certification(
                crew_member_id=pending.id,
                cert_type="OGUK Medical",
                status="pending_verification",
                verification_status="unverified",
                expiry_date=date.today() + timedelta(days=365),
            ),
            Certification(
                crew_member_id=valid.id,
                cert_type="OGUK Medical",
                status="valid",
                verification_status="verified",
                expiry_date=date.today() + timedelta(days=365),
            ),
            Certification(
                crew_member_id=expiring.id,
                cert_type="OGUK Medical",
                status="expiring_soon",
                verification_status="verified",
                expiry_date=date.today() + timedelta(days=10),
            ),
            Certification(
                crew_member_id=missing_expiry.id,
                cert_type="OGUK Medical",
                status="valid",
                verification_status="verified",
                expiry_date=None,
            ),
            Certification(
                crew_member_id=unverified_valid.id,
                cert_type="OGUK Medical",
                status="valid",
                verification_status="unverified",
                expiry_date=date.today() + timedelta(days=365),
            ),
        ]
    )
    await db_session.commit()

    result = await CrewQueryService()._handle_search(
        "Who has a current medical?",
        {
            "medical_required": True,
            "medical_valid": True,
            "certifications": ["OGUK Medical"],
        },
        db_session,
    )

    result_ids = {candidate["id"] for candidate in result["results"]}
    assert valid.id in result_ids
    assert expiring.id in result_ids
    assert missing_expiry.id not in result_ids
    assert pending.id not in result_ids
    assert unverified_valid.id not in result_ids


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
        professional_summary="Offshore wind survey specialist based near Aberdeen, Scotland.",
        geographical_experience=["Aberdeen, Scotland"],
        country_of_residence="Norway",
        languages=["English", "Norwegian"],
    )
    unavailable = CrewMember(
        full_name="Search Matrix Unavailable",
        email="matrix-unavailable@example.com",
        availability_status="unavailable",
    )
    db_session.add_all([medic, surveyor, unavailable])
    await db_session.flush()
    db_session.add_all(
        [
            Certification(crew_member_id=medic.id, cert_type="OGUK Medical"),
            Certification(crew_member_id=surveyor.id, cert_type="BOSIET"),
        ]
    )
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
        ("Show specialists in Norway", {"location": "Norway"}, surveyor.id),
        ("Find Norwegian-speaking crew", {"skills": ["Norwegian"]}, surveyor.id),
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

    assert "email" not in result["results"][0]
    assert "work_locations" not in result["results"][0]


@pytest.mark.asyncio
async def test_t1_query_cannot_use_compliance_intent(db_session):
    service = CrewQueryService()
    service._classify_intent = AsyncMock(return_value={"intent": "compliance", "entities": {}})

    result = await service.process_query(
        "Which specialists have expiring certificates?",
        db_session,
        allow_compliance=False,
    )

    assert result["results"] == []
    assert result["total_issues"] == 0
    assert "staff access" in result["summary"]


@pytest.mark.asyncio
async def test_search_preserves_missing_experience_as_null(db_session):
    crew = CrewMember(
        full_name="Search Missing Experience",
        email="missing-experience@example.com",
        publication_status="approved",
        experience_months=None,
    )
    db_session.add(crew)
    await db_session.commit()

    result = await CrewQueryService()._handle_search("Find specialists", {}, db_session)

    candidate = next(item for item in result["results"] if item["id"] == crew.id)
    assert candidate["experience_years"] is None


@pytest.mark.asyncio
async def test_summarize_ambiguous_name_does_not_crash_or_choose_arbitrary_profile(db_session):
    """Fuzzy summarize requests must fail safely when names overlap."""
    db_session.add_all(
        [
            CrewMember(full_name="Summary Ambiguous Alex Carter"),
            CrewMember(full_name="Summary Ambiguous Alex Carter Jr"),
        ]
    )
    await db_session.commit()

    service = CrewQueryService()
    result = await service._handle_summarize(
        "Summarize Summary Ambiguous Alex",
        {"crew_name": "Summary Ambiguous Alex"},
        db_session,
    )

    assert result["summary"].startswith("More than one approved specialist")
    assert "crew_id" not in result


@pytest.mark.asyncio
async def test_compliance_search_excludes_rejected_and_non_issue_certificates(db_session):
    flagged = CrewMember(
        full_name="Compliance Flagged",
        publication_status="approved",
    )
    rejected = CrewMember(
        full_name="Compliance Rejected",
        publication_status="approved",
    )
    unrelated = CrewMember(
        full_name="Compliance Unrelated",
        publication_status="approved",
    )
    account = CrewMember(
        full_name="Admin Login Account",
        role="admin",
        password_hash="stored-password-hash",
        publication_status="approved",
    )
    db_session.add_all([flagged, rejected, unrelated, account])
    await db_session.flush()
    db_session.add_all(
        [
            Certification(
                crew_member_id=flagged.id,
                cert_type="BOSIET",
                status="expired",
                verification_status="verified",
                expiry_date=date.today() - timedelta(days=1),
            ),
            Certification(
                crew_member_id=rejected.id,
                cert_type="Medical",
                status="expired",
                verification_status="rejected",
                expiry_date=date.today() - timedelta(days=1),
            ),
            Certification(
                crew_member_id=unrelated.id,
                cert_type="STCW",
                status="valid",
                expiry_date=date.today() + timedelta(days=10),
            ),
            Certification(
                crew_member_id=account.id,
                cert_type="BOSIET",
                status="expired",
                verification_status="verified",
                expiry_date=date.today() - timedelta(days=1),
            ),
        ]
    )
    await db_session.commit()

    result = await CrewQueryService()._handle_compliance(
        "Which specialists have expiring certificates?",
        {},
        db_session,
    )

    assert [item["id"] for item in result["results"]] == [flagged.id]


def test_compliance_status_uses_expiry_date_over_stale_persisted_status():
    reference_date = date(2026, 9, 13)

    assert _derived_compliance_status(date(2027, 9, 13), "expiring_soon", reference_date) is None
    assert _derived_compliance_status(date(2026, 9, 12), "valid", reference_date) == "expired"


@pytest.mark.asyncio
async def test_valid_certificate_and_availability_date_are_enforced(db_session):
    eligible = CrewMember(
        full_name="Eligible Medic",
        availability_status="available",
        availability_date=date.today() + timedelta(days=10),
        tags=["offshore medic"],
    )
    stale_status = CrewMember(
        full_name="Stale Status Medic",
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
    rejected = CrewMember(
        full_name="Rejected Medic",
        availability_status="available",
        availability_date=date.today() + timedelta(days=10),
        tags=["offshore medic"],
    )
    verification_rejected = CrewMember(
        full_name="Verification Rejected Medic",
        availability_status="available",
        availability_date=date.today() + timedelta(days=10),
        tags=["offshore medic"],
    )
    db_session.add_all([eligible, stale_status, expired, rejected, verification_rejected])
    await db_session.flush()
    db_session.add_all(
        [
            Certification(
                crew_member_id=eligible.id,
                cert_type="BOSIET",
                status="valid",
                verification_status="verified",
                expiry_date=date.today() + timedelta(days=120),
            ),
            Certification(
                crew_member_id=stale_status.id,
                cert_type="BOSIET",
                status="expired",
                verification_status="verified",
                expiry_date=date.today() + timedelta(days=120),
            ),
            Certification(
                crew_member_id=eligible.id,
                cert_type="Rejected STCW",
                status="rejected",
            ),
            Certification(
                crew_member_id=expired.id,
                cert_type="BOSIET",
                expiry_date=date.today() - timedelta(days=1),
            ),
            Certification(
                crew_member_id=rejected.id,
                cert_type="BOSIET",
                expiry_date=date.today() + timedelta(days=120),
                status="rejected",
            ),
            Certification(
                crew_member_id=verification_rejected.id,
                cert_type="BOSIET",
                expiry_date=date.today() + timedelta(days=120),
                status="valid",
                verification_status="rejected",
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

    assert {candidate["id"] for candidate in result["results"]} == {
        eligible.id,
        stale_status.id,
    }
    assert all(candidate["certifications"] == ["BOSIET"] for candidate in result["results"])

    ordinary_result = await service._handle_search(
        "Find BOSIET specialists",
        {"certifications": ["BOSIET"]},
        db_session,
    )
    assert rejected.id not in {candidate["id"] for candidate in ordinary_result["results"]}
    assert verification_rejected.id not in {
        candidate["id"] for candidate in ordinary_result["results"]
    }


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


def test_validate_llm_response_does_not_log_untrusted_values(caplog):
    secret_value = "private search content that must not enter logs"

    with caplog.at_level("WARNING"):
        _validate_llm_response(
            {
                "entities": {
                    "nationality": {"raw": secret_value},
                    "min_experience_years": {"raw": secret_value},
                }
            }
        )

    assert secret_value not in caplog.text
    assert "type=dict" in caplog.text


def test_validate_llm_response_drops_non_finite_or_unreasonable_experience():
    validated = _validate_llm_response(
        {
            "intent": "search",
            "entities": {
                "min_experience_years": float("inf"),
                "max_experience_years": 101,
            },
        }
    )
    assert "min_experience_years" not in validated["entities"]
    assert "max_experience_years" not in validated["entities"]
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


def test_validate_llm_response_bounds_filter_values_and_rejects_boolean_numbers():
    validated = _validate_llm_response(
        {
            "intent": "search",
            "entities": {
                "certifications": ["  BOSIET  ", "x" * 256, *[f"cert-{i}" for i in range(100)]],
                "crew_name": "x" * 256,
                "min_experience_years": True,
            },
            "confidence": False,
        }
    )

    assert validated["entities"]["certifications"][0] == "BOSIET"
    assert len(validated["entities"]["certifications"]) == 50
    assert "crew_name" not in validated["entities"]
    assert "min_experience_years" not in validated["entities"]
    assert validated["confidence"] is None
