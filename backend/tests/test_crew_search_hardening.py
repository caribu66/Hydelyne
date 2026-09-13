"""Hardening test suite for relational crew member search.

Verifies that CrewService.list_crew_members is resilient against:
- SQL injection payloads
- Wildcard character abuse (%, _, \\)
- Special symbols and punctuation
- Extremely long payload inputs (overflow/DoS resilience)
- Unicode and emojis
- Case-insensitivity across full name, tags, certifications, and work history
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import patch

import pytest

from app.models import Certification, CrewMember, WorkHistory
from app.services.crew import CrewService, _contains_like


def test_roster_query_text_is_literal_when_used_in_sql_like_patterns() -> None:
    assert _contains_like(r"100%_ready\now") == r"%100\%\_ready\\now%"


async def _create_test_crew_member(
    db_session: Any,
    full_name: str,
    email: str,
    nationality: str = "British",
    country_of_residence: str | None = None,
    languages: list[str] | None = None,
    summary: str = "Experienced offshore specialist",
    tags: list[str] | None = None,
    cert_types: list[str] | None = None,
    work_roles: list[str] | None = None,
) -> CrewMember:
    crew = CrewMember(
        id=str(uuid.uuid4()),
        full_name=full_name,
        email=email,
        nationality=nationality,
        country_of_residence=country_of_residence,
        languages=languages,
        professional_summary=summary,
        tags=tags or [],
        publication_status="approved",
        role="user",
        availability_status="available",
    )
    db_session.add(crew)
    await db_session.flush()

    for ct in cert_types or []:
        cert = Certification(
            id=str(uuid.uuid4()),
            crew_member_id=crew.id,
            cert_type=ct,
            status="valid",
            expiry_date=date(2028, 1, 1),
        )
        db_session.add(cert)

    for wr in work_roles or []:
        wh = WorkHistory(
            id=str(uuid.uuid4()),
            crew_member_id=crew.id,
            client_name="Test Client",
            project_name="Test Survey",
            project_type="marine_seismic",
            role=wr,
            status="completed",
        )
        db_session.add(wh)

    await db_session.commit()
    await db_session.refresh(crew)
    return crew


@pytest.mark.asyncio
async def test_search_handles_sql_injection_payloads(db_session: Any) -> None:
    """Verifies that SQL injection strings return safe matches without errors or data leaks."""
    crew = await _create_test_crew_member(
        db_session,
        full_name="Injection Target",
        email="target@example.com",
    )

    svc = CrewService()
    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        injection_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE crew_members; --",
            "admin' --",
            '" OR ""="',
            "1' UNION SELECT NULL, NULL, NULL--",
            "'; WAITFOR DELAY '0:0:5'--",
            "1 AND 1=1",
        ]

        for payload in injection_payloads:
            results = await svc.list_crew_members(search=payload)
            # None of the injection payloads should match the crew or throw an exception
            assert isinstance(results, list)
            assert not any(c.id == crew.id for c in results)


@pytest.mark.asyncio
async def test_search_handles_wildcard_characters_safely(db_session: Any) -> None:
    """Special LIKE wildcards must not cause server errors."""
    await _create_test_crew_member(
        db_session,
        full_name="Percent%Special",
        email="percent@example.com",
    )

    svc = CrewService()
    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        wildcards = ["%", "%%", "___", "\\", "%_%", "[a-z]", "*", "?", "+"]
        for wc in wildcards:
            results = await svc.list_crew_members(search=wc)
            assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_handles_extremely_long_strings(db_session: Any) -> None:
    """Very large search payloads must not crash or cause unbounded resource spikes."""
    await _create_test_crew_member(
        db_session,
        full_name="Standard Specialist",
        email="standard@example.com",
    )

    svc = CrewService()
    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        huge_payload = "A" * 10000
        results = await svc.list_crew_members(search=huge_payload)
        assert results == []


@pytest.mark.asyncio
async def test_search_handles_unicode_and_emojis(db_session: Any) -> None:
    """Unicode text, foreign alphabets, and emojis are handled cleanly."""
    crew = await _create_test_crew_member(
        db_session,
        full_name="Björn O'Connor-Müller",
        email="bjorn@example.com",
        nationality="Norwegian",
        summary="Spécialiste géophysique offshore",
        tags=["Deepwater Navigator", "Seismic QC"],
    )

    svc = CrewService()
    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        # 1. Search with umlaut / special char in full name
        res1 = await svc.list_crew_members(search="Björn")
        assert any(c.id == crew.id for c in res1)

        # 2. Search with accented word in professional summary
        res2 = await svc.list_crew_members(search="géophysique")
        assert any(c.id == crew.id for c in res2)

        # 3. Non-matching foreign characters
        res3 = await svc.list_crew_members(search="こんにちは")
        assert not any(c.id == crew.id for c in res3)


@pytest.mark.asyncio
async def test_search_matches_relational_certifications(db_session: Any) -> None:
    """Querying by certification type matches crew members having that certificate."""
    crew = await _create_test_crew_member(
        db_session,
        full_name="Hydro Specialist",
        email="hydro@example.com",
        cert_types=["IHO Cat A Hydrographer", "Multibeam Bathymetry"],
    )

    svc = CrewService()
    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        res = await svc.list_crew_members(search="Cat A Hydrographer")
        assert any(c.id == crew.id for c in res)

        res_partial = await svc.list_crew_members(search="bathymetry")
        assert any(c.id == crew.id for c in res_partial)


@pytest.mark.asyncio
async def test_search_matches_country_of_residence_and_languages(db_session: Any) -> None:
    """Public roster search includes searchable profile location and languages."""
    crew = await _create_test_crew_member(
        db_session,
        full_name="Multilingual Survey Specialist",
        email="multilingual@example.com",
        country_of_residence="Norway",
        languages=["English", "Norwegian"],
    )

    svc = CrewService()
    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        country_results = await svc.list_crew_members(search="Norway")
        language_results = await svc.list_crew_members(search="Norwegian")

    assert any(member.id == crew.id for member in country_results)
    assert any(member.id == crew.id for member in language_results)


@pytest.mark.asyncio
async def test_search_ignores_rejected_certifications(db_session: Any) -> None:
    """Declined evidence must not make a contractor match a qualification search."""
    crew = await _create_test_crew_member(
        db_session,
        full_name="Declined Evidence Specialist",
        email="declined@example.com",
    )
    db_session.add(
        Certification(
            id=str(uuid.uuid4()),
            crew_member_id=crew.id,
            cert_type="Rejected BOSIET",
            status="rejected",
            verification_status="rejected",
        )
    )
    await db_session.commit()

    svc = CrewService()
    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        results = await svc.list_crew_members(search="BOSIET")

    assert not any(member.id == crew.id for member in results)


@pytest.mark.asyncio
async def test_search_does_not_match_restricted_work_history_or_email(db_session: Any) -> None:
    """General roster search cannot use C2 fields as a discovery side channel."""
    crew = await _create_test_crew_member(
        db_session,
        full_name="Survey Veteran",
        email="veteran@example.com",
        work_roles=["Lead Party Chief", "Senior OBN Geophysicist"],
    )

    svc = CrewService()
    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        res1 = await svc.list_crew_members(search="Party Chief")
        assert not any(c.id == crew.id for c in res1)

        res2 = await svc.list_crew_members(search="veteran@example.com")
        assert not any(c.id == crew.id for c in res2)


@pytest.mark.asyncio
async def test_search_empty_and_whitespace_only(db_session: Any) -> None:
    """Empty or whitespace-only search does not filter out approved crew members."""
    crew = await _create_test_crew_member(
        db_session,
        full_name="Whitespace Test",
        email="whitespace@example.com",
    )

    svc = CrewService()
    with patch("app.services.crew.get_session_factory", return_value=lambda: db_session):
        res_none = await svc.list_crew_members(search=None)
        assert any(c.id == crew.id for c in res_none)

        # Empty string should not fail
        res_empty = await svc.list_crew_members(search="")
        assert any(c.id == crew.id for c in res_empty)

        # Whitespace-only string should be stripped cleanly and behave like empty/all
        res_spaces = await svc.list_crew_members(search="   ")
        assert any(c.id == crew.id for c in res_spaces)
