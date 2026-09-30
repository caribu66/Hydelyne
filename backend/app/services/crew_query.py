from __future__ import annotations

import json
import logging
import math
from datetime import date, timedelta
from typing import Any, TypedDict

import sqlalchemy as sa
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.domain.certifications import normalize_cert_name
from app.domain.crew_query_rules import MAX_SEARCH_QUERY_LENGTH, apply_deterministic_query_rules
from app.models import Certification as CertificationModel
from app.models import CrewMember as CrewMemberModel
from app.services.ollama import ollama_client

logger = logging.getLogger(__name__)
MAX_GENERATED_RESPONSE_LENGTH = 12_000
MAX_INTENT_RESPONSE_LENGTH = 20_000


class CrewQueryEntities(TypedDict, total=False):
    certifications: list[str]
    skills: list[str]
    location: str | None
    nationality: str | None
    certification_keywords: list[str]
    min_experience_years: float | None
    max_experience_years: float | None
    availability: str | None
    availability_by: str | None
    project_type: str | None
    crew_name: str | None
    medical_required: bool | None
    medical_valid: bool | None
    certifications_valid: bool | None


class CrewQueryLLMResponse(TypedDict, total=False):
    intent: str
    entities: CrewQueryEntities
    confidence: float | None


_INTENT_VALUES = {"search", "summarize", "compliance", "matching", "general"}
_AVAILABILITY_VALUES = {"available immediately", "available", "unavailable", "on assignment"}
MAX_QUERY_ENTITY_VALUE_LENGTH = 255
MAX_QUERY_ENTITY_LIST_ITEMS = 50


def _bounded_entity_values(value: object) -> list[str]:
    """Keep model-produced filter values scalar, bounded, and finite."""
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized and len(normalized) <= MAX_QUERY_ENTITY_VALUE_LENGTH:
            values.append(normalized)
        if len(values) >= MAX_QUERY_ENTITY_LIST_ITEMS:
            break
    return list(dict.fromkeys(values))


def _bounded_entity_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_QUERY_ENTITY_VALUE_LENGTH:
        return None
    return normalized


def _contains_like(value: str) -> str:
    """Build a literal substring pattern for a SQL ``LIKE`` expression."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _experience_years(experience_months: int | None) -> float | None:
    """Convert stored experience without turning an unknown value into zero."""
    if experience_months is None:
        return None
    return round(experience_months / 12, 1)


def _derived_compliance_status(
    expiry_date: date | None,
    stored_status: str | None,
    reference_date: date,
) -> str | None:
    """Derive compliance state from expiry evidence, not stale status text."""
    if expiry_date is None:
        return stored_status if stored_status in {"expired", "expiring_soon"} else None
    if expiry_date < reference_date:
        return "expired"
    if expiry_date <= reference_date + timedelta(days=90):
        return "expiring_soon"
    return None


def _not_explicitly_rejected(
    column: ColumnElement[Any] | InstrumentedAttribute[Any],
) -> ColumnElement[bool]:
    """Treat legacy NULL lifecycle values as not explicitly rejected."""
    return or_(column.is_(None), column != "rejected")


def _contractor_account_condition() -> ColumnElement[bool]:
    """Keep login accounts out of natural-language contractor retrieval."""
    return and_(
        CrewMemberModel.password_hash.is_(None),
        or_(CrewMemberModel.role.is_(None), CrewMemberModel.role.not_in(("staff", "admin"))),
    )


def _validate_llm_response(raw: dict[str, Any]) -> CrewQueryLLMResponse:
    """Validate and sanitize the LLM classification payload.

    The local Ollama model is instructed to return a fixed JSON shape, but
    LLM output is untrusted input. This function enforces the expected types
    and drops malformed values rather than propagating them into database
    filters.
    """
    if not isinstance(raw, dict):
        raise ValueError("Intent classifier returned a non-object response")

    intent = raw.get("intent", "general")
    if not isinstance(intent, str) or intent not in _INTENT_VALUES:
        intent = "general"

    entities = raw.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}

    certified: CrewQueryEntities = {}
    for field in (
        "certifications",
        "skills",
        "certification_keywords",
    ):
        value = entities.get(field)
        if isinstance(value, list):
            bounded_values = _bounded_entity_values(value)
            if bounded_values:
                certified[field] = bounded_values  # type: ignore[literal-required]
        elif value is not None:
            logger.warning(
                "Ignoring malformed LLM entities.%s (type=%s)", field, type(value).__name__
            )

    for field in (
        "location",
        "nationality",
        "project_type",
        "crew_name",
        "availability",
        "availability_by",
    ):
        value = entities.get(field)
        bounded_value = _bounded_entity_value(value)
        if bounded_value is not None:
            certified[field] = bounded_value  # type: ignore[literal-required]
        elif value is not None:
            logger.warning(
                "Ignoring malformed LLM entities.%s (type=%s)", field, type(value).__name__
            )

    for field in ("min_experience_years", "max_experience_years"):
        value = entities.get(field)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and 0 <= value <= 100
        ):
            certified[field] = float(value)  # type: ignore[literal-required]
        elif value is not None:
            logger.warning(
                "Ignoring malformed LLM entities.%s (type=%s)", field, type(value).__name__
            )

    for field in ("medical_required", "medical_valid", "certifications_valid"):
        value = entities.get(field)
        if isinstance(value, bool):
            certified[field] = value  # type: ignore[literal-required]
        elif value is not None:
            logger.warning(
                "Ignoring malformed LLM entities.%s (type=%s)", field, type(value).__name__
            )

    if certified.get("availability") not in _AVAILABILITY_VALUES:
        certified.pop("availability", None)

    confidence = raw.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(float(confidence))
        or not (0.0 <= float(confidence) <= 1.0)
    ):
        confidence = None

    return CrewQueryLLMResponse(intent=intent, entities=certified, confidence=confidence)


CREW_QUERY_PROMPTS = {
    "intent_classification": """Classify the user's query about crew members into one of these intents:

- search: Finding crew members based on criteria (certifications, skills, location, availability, experience)
- summarize: Getting a summary of a specific crew member's profile/experience
- compliance: Checking certification status, expired documents, medical fitness, expiring certifications
- matching: Finding the best candidate for a project or role
- general: General information or other queries

Return JSON:
{{
  "intent": "search|summarize|compliance|matching|general",
  "entities": {{
    "certifications": ["exact cert type from: BOSIET, STCW, OGUK Medical, GWO Wind, NEBOSH Diploma, IHO Cat A Hydrographer, IMCA Survey QC, PAMGUARD Advanced, EOD Level 3, JNCC MMO, IMCA Geotech, IOGP Geophysical Rep, IMCA Client Rep, NCS Safety, ISO 45001 Lead Auditor, CPT Testing, Vibrocoring, UXO QC, ROV Video Verification, Seismic Data Processing, Multibeam Bathymetry, Side Scan Sonar, QPS QINSy, Foundation Engineering, Hydrophone Arrays, Harbour Porpoise Detection, HSE Advisory, Safety Case Compliance, Offshore Medic, HUET, CA-EBS, FOET"],
    "skills": ["offshore", "subsea", "survey", "geophysics", "hydrography", "ROV", "diving", "environmental", "PAM", "wind farm", "oil & gas", "marine", "construction", "inspection"],
    "location": "location if mentioned (country, region, or city)",
    "nationality": "nationality if mentioned (for example Spanish or Norwegian)",
    "certification_keywords": ["credential families explicitly requested, e.g. IMCA"],
    "min_experience_years": "minimum whole or decimal years of experience, or null",
    "max_experience_years": "maximum years only when the user says exactly or at most, or null",
    "availability": "available immediately|available|unavailable",
    "project_type": "type of project or experience (e.g., offshore, subsea, wind farm, seismic survey, environmental monitoring)",
    "crew_name": "name of specific crew member if mentioned",
    "medical_required": true|false,
    "medical_valid": true|false
  }},
  "confidence": 0.0-1.0
}}

IMPORTANT:
- For "offshore experience", "offshore work", "offshore background" → set skills to ["offshore"] and/or project_type to "offshore"
- For "subsea", "renewables", "wind farm" → add to skills array
- For compliance intent, use when query contains words like: expired, expiring, compliance, medical expired, renew, renewal, non-compliant
- For a non-expiry medical query (for example "who has a medical" or "medical experience"), set intent to search and medical_required to true. This means a current or recorded offshore medical.
- For "current medical", "valid medical", or "in-date medical", also set medical_valid to true.
- For a qualification family such as IMCA, put the family in certification_keywords. Do not invent an exact certificate called "IMCA".
- For "3 years of experience" set min_experience_years to 3. Set both minimum and maximum to 3 only when the user says "exactly 3 years".

Query: {query}""",
    "search_response": """Based on the following crew search results, provide a helpful summary in 2-3 sentences.

Query: {query}

Crew Results:
{results}

Provide a concise summary of matching crew members, highlighting their key qualifications and relevance to the query.""",
    "summarize_response": """You are writing a short professional profile summary of a crew
member, to be read by a client or project manager.

Write 2-4 flowing paragraphs of plain prose in your own words. Do not
output JSON, bullet points, markdown headers, or a code block. Do not
copy the raw data fields or their labels verbatim — describe the person
naturally, the way you would introduce them to a colleague.

Cover, where the data supports it:
- Key qualifications and certifications
- Relevant experience highlights
- Specializations
- Availability status

Crew member data (reference only — do not copy this structure or its
field names into your answer):
{results}

Document extractions (reference only):
{document_data}

Write the paragraph summary now:""",
    "compliance_response": """Analyze the compliance status and provide actionable insights.

Query: {query}

Compliance Data:
{results}

Highlight:
- Critical issues (expired certifications)
- Upcoming expirations (within 90 days)
- Compliance percentage
- Recommended actions""",
    "matching_response": """Rank and explain the best candidates for this project/role.

Query: {query}

Candidate Data:
{results}

For each candidate, provide:
- Match score (1-10)
- Key strengths for this role
- Any gaps or concerns
- Overall recommendation""",
}


class CrewQueryService:
    """Service for natural language queries about crew members."""

    async def process_query(
        self,
        query: str,
        db_session: AsyncSession,
        *,
        allow_compliance: bool = True,
    ) -> dict[str, Any]:
        """Process a natural language query about crew members."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query must not be blank")
        if len(normalized_query) > MAX_SEARCH_QUERY_LENGTH:
            raise ValueError(f"Search query must be {MAX_SEARCH_QUERY_LENGTH} characters or fewer")
        query = normalized_query
        intent_result = await self._classify_intent(query)
        intent = intent_result.get("intent", "general")
        entities = intent_result.get("entities", {})

        if intent == "compliance" and not allow_compliance:
            return {
                "intent": "compliance",
                "query": query,
                "entities": entities,
                "results": [],
                "summary": "Compliance searches require staff access.",
                "total_issues": 0,
            }

        if intent == "search":
            response = await self._handle_search(query, entities, db_session)
        elif intent == "summarize":
            response = await self._handle_summarize(query, entities, db_session)
        elif intent == "compliance":
            response = await self._handle_compliance(query, entities, db_session)
        elif intent == "matching":
            response = await self._handle_matching(query, entities, db_session)
        else:
            response = await self._handle_general(query, db_session)

        # Expose the structured interpretation so agents can audit exactly
        # which requirements determined the candidate list.
        response["criteria"] = entities
        return response

    async def _classify_intent(self, query: str) -> dict[str, Any]:
        """Classify the user's query intent."""
        prompt = CREW_QUERY_PROMPTS["intent_classification"].format(query=query)
        try:
            result = await ollama_client.extract(prompt)
            response_text = result.get("response", "")
            if (
                not isinstance(response_text, str)
                or len(response_text) > MAX_INTENT_RESPONSE_LENGTH
            ):
                raise ValueError("Intent classifier response is invalid or too large")
            classified = json.loads(response_text)
            validated = _validate_llm_response(classified)
            return apply_deterministic_query_rules(query, dict(validated))
        except Exception as e:
            logger.error("Intent classification failed: %s", type(e).__name__)
            # Search remains useful when the local model is unavailable.
            return apply_deterministic_query_rules(
                query, {"intent": "search", "entities": {}, "confidence": 0.0}
            )

    async def _handle_search(
        self, query: str, entities: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        """Handle search/filter queries with broad matching across crew data."""
        stmt = (
            select(CrewMemberModel)
            .where(CrewMemberModel.publication_status == "approved")
            .where(_contractor_account_condition())
            .options(
                selectinload(CrewMemberModel.certifications),
            )
        )

        filters: list[ColumnElement[bool]] = []
        search_terms = []

        # Medical certification type and expiry are C1 searchable fields;
        # dedicated medical columns are C3 and must not be a T1 side channel.
        if entities.get("medical_required"):
            if entities.get("medical_valid"):
                filters.append(
                    or_(
                        CrewMemberModel.certifications.any(
                            and_(
                                or_(
                                    CertificationModel.cert_type.ilike("%medical%"),
                                    CertificationModel.cert_type.ilike("%oguk%"),
                                    CertificationModel.cert_type.ilike("%oeuk%"),
                                    CertificationModel.cert_type.ilike("%eng1%"),
                                ),
                                _not_explicitly_rejected(CertificationModel.status),
                                CertificationModel.verification_status == "verified",
                                CertificationModel.expiry_date.is_not(None),
                                CertificationModel.expiry_date >= date.today(),
                            )
                        ),
                    )
                )
            else:
                filters.append(
                    or_(
                        CrewMemberModel.certifications.any(
                            and_(
                                or_(
                                    CertificationModel.cert_type.ilike("%medical%"),
                                    CertificationModel.cert_type.ilike("%oguk%"),
                                    CertificationModel.cert_type.ilike("%oeuk%"),
                                    CertificationModel.cert_type.ilike("%eng1%"),
                                ),
                                _not_explicitly_rejected(CertificationModel.status),
                                _not_explicitly_rejected(CertificationModel.verification_status),
                            )
                        ),
                    )
                )

        if entities.get("nationality"):
            filters.append(
                CrewMemberModel.nationality.ilike(
                    _contains_like(str(entities["nationality"])), escape="\\"
                )
            )

        if entities.get("min_experience_years") is not None:
            filters.append(
                CrewMemberModel.experience_months
                >= int(float(entities["min_experience_years"]) * 12)
            )
        if entities.get("max_experience_years") is not None:
            filters.append(
                CrewMemberModel.experience_months
                <= int(float(entities["max_experience_years"]) * 12)
            )

        # A credential family (such as IMCA) matches every concrete member of
        # that family: IMCA Survey QC, IMCA Geotech, IMCA Client Rep, etc.
        for keyword in entities.get("certification_keywords") or []:
            family_conditions: list[ColumnElement[bool]] = [
                CertificationModel.cert_type.ilike(_contains_like(str(keyword)), escape="\\"),
                _not_explicitly_rejected(CertificationModel.status),
                _not_explicitly_rejected(CertificationModel.verification_status),
            ]
            if entities.get("certifications_valid"):
                family_conditions.extend(
                    [
                        CertificationModel.verification_status == "verified",
                        CertificationModel.expiry_date.is_not(None),
                        CertificationModel.expiry_date >= date.today(),
                    ]
                )
            filters.append(CrewMemberModel.certifications.any(and_(*family_conditions)))

        # Extract searchable terms from entities
        if entities.get("certifications"):
            cert_types = entities["certifications"]
            normalized_certs = [normalize_cert_name(c) for c in cert_types]
            # medical_required already searches both certification records and
            # the dedicated medical fields above. Avoid narrowing that OR back
            # to certification-only when the model also names OGUK Medical.
            if entities.get("medical_required"):
                normalized_certs = [
                    cert for cert in normalized_certs if "medical" not in cert.lower()
                ]
            family_keywords = {
                str(keyword).upper() for keyword in entities.get("certification_keywords") or []
            }
            # An LLM may echo "IMCA" into certifications as well as the
            # family field. It is not an exact database certificate; leave
            # family matching to the ILIKE condition above.
            normalized_certs = [
                cert for cert in normalized_certs if cert.upper() not in family_keywords
            ]
            # Each named certification is a requirement, not an alternative.
            # Separate EXISTS clauses preserve AND semantics for queries such
            # as "BOSIET and OGUK Medical".
            for cert_type in normalized_certs:
                cert_conditions: list[ColumnElement[bool]] = [
                    CertificationModel.cert_type == cert_type,
                    _not_explicitly_rejected(CertificationModel.status),
                    _not_explicitly_rejected(CertificationModel.verification_status),
                ]
                if entities.get("certifications_valid"):
                    cert_conditions.extend(
                        [
                            CertificationModel.verification_status == "verified",
                            CertificationModel.expiry_date.is_not(None),
                            CertificationModel.expiry_date >= date.today(),
                        ]
                    )
                filters.append(CrewMemberModel.certifications.any(and_(*cert_conditions)))

        # Skills become broad text search terms
        if entities.get("skills"):
            search_terms.extend(entities["skills"])

        # Project type maps to work history
        if entities.get("project_type"):
            search_terms.append(entities["project_type"])

        # Location search across work history
        if entities.get("location"):
            search_terms.append(entities["location"])

        # Availability filter
        if entities.get("availability") == "available immediately":
            filters.append(CrewMemberModel.availability_status == "available")
        elif entities.get("availability") == "available":
            filters.append(CrewMemberModel.availability_status == "available")
        elif entities.get("availability") == "unavailable":
            filters.append(CrewMemberModel.availability_status == "unavailable")
        elif entities.get("availability") == "on assignment":
            filters.append(CrewMemberModel.availability_status == "on_assignment")
        availability_by = entities.get("availability_by")
        if isinstance(availability_by, str):
            try:
                latest_date = date.fromisoformat(availability_by)
            except ValueError:
                latest_date = None
            if latest_date is not None:
                filters.append(
                    or_(
                        CrewMemberModel.availability_date.is_(None),
                        CrewMemberModel.availability_date <= latest_date,
                    )
                )

        # Broad text search across multiple fields
        if search_terms:
            for term in search_terms:
                term_filters: list[ColumnElement[bool]] = []
                like_pattern = _contains_like(str(term))
                term_filters.append(CrewMemberModel.full_name.ilike(like_pattern, escape="\\"))
                term_filters.append(
                    sa.cast(CrewMemberModel.tags, sa.String).ilike(like_pattern, escape="\\")
                )
                # Natural search is a T1/C1 surface. Do not use internal notes
                # or work-history rows here; matching on either would let a
                # caller infer restricted data even if the result is scrubbed.
                term_filters.extend(
                    [
                        CrewMemberModel.nationality.ilike(like_pattern, escape="\\"),
                        CrewMemberModel.country_of_residence.ilike(like_pattern, escape="\\"),
                        sa.cast(CrewMemberModel.languages, sa.String).ilike(
                            like_pattern, escape="\\"
                        ),
                        CrewMemberModel.flying_point.ilike(like_pattern, escape="\\"),
                        CrewMemberModel.professional_summary.ilike(like_pattern, escape="\\"),
                        CrewMemberModel.education.ilike(like_pattern, escape="\\"),
                        sa.cast(CrewMemberModel.geographical_experience, sa.String).ilike(
                            like_pattern, escape="\\"
                        ),
                        sa.cast(CrewMemberModel.systems_experience, sa.String).ilike(
                            like_pattern, escape="\\"
                        ),
                        sa.cast(CrewMemberModel.training_qualifications, sa.String).ilike(
                            like_pattern, escape="\\"
                        ),
                    ]
                )
                # Certification type names
                term_filters.append(
                    CrewMemberModel.certifications.any(
                        and_(
                            CertificationModel.cert_type.ilike(like_pattern, escape="\\"),
                            _not_explicitly_rejected(CertificationModel.status),
                            _not_explicitly_rejected(CertificationModel.verification_status),
                        )
                    )
                )
                # Also split multi-word terms for partial matching
                words = term.split()
                if len(words) > 1:
                    for word in words:
                        if len(word) > 3:  # Skip short words
                            term_filters.append(
                                CrewMemberModel.certifications.any(
                                    and_(
                                        CertificationModel.cert_type.ilike(
                                            _contains_like(str(word)), escape="\\"
                                        ),
                                        _not_explicitly_rejected(CertificationModel.status),
                                        _not_explicitly_rejected(
                                            CertificationModel.verification_status
                                        ),
                                    )
                                )
                            )
                            term_filters.append(
                                sa.cast(CrewMemberModel.tags, sa.String).ilike(
                                    _contains_like(str(word)), escape="\\"
                                )
                            )
                # Each requested skill/location/project term is a requirement;
                # the OR applies only to the fields where that term may be
                # evidenced. This prevents a match on "offshore" alone from
                # being presented as evidence of "offshore medic" experience.
                filters.append(or_(*term_filters))

        if filters:
            stmt = stmt.where(and_(*filters))

        # Rank in SQL before the limit so the top-20 are the global
        # best, not the best of an arbitrary first-20 slice.
        stmt = stmt.order_by(
            (CrewMemberModel.availability_status == "available").desc(),
            CrewMemberModel.experience_months.desc().nulls_last(),
            CrewMemberModel.profile_completeness_score.desc().nulls_last(),
        )
        result = await db_session.execute(stmt.limit(20))
        crew_list = list(result.scalars().unique().all())

        if not crew_list:
            return {
                "intent": "search",
                "query": query,
                "results": [],
                "summary": "No specialists meet every requirement.",
            }

        results_data = []
        for crew in crew_list:
            results_data.append(
                {
                    "id": crew.id,
                    "name": crew.full_name,
                    "availability": crew.availability_status,
                    "experience_years": _experience_years(crew.experience_months),
                    "nationality": crew.nationality,
                    "country_of_residence": crew.country_of_residence,
                    "languages": crew.languages or [],
                    "flying_point": crew.flying_point,
                    "education": crew.education,
                    "tags": crew.tags or [],
                    "training_qualifications": crew.training_qualifications or [],
                    "geographical_experience": crew.geographical_experience or [],
                    "systems_experience": crew.systems_experience or [],
                    "certifications": [
                        c.cert_type
                        for c in crew.certifications
                        if (c.status is None or c.status != "rejected")
                        and (c.verification_status is None or c.verification_status != "rejected")
                    ],
                }
            )

        return {
            "intent": "search",
            "query": query,
            "results": results_data,
            # Structured search should be immediate and predictable. A short
            # deterministic outcome is more useful here than a delayed LLM
            # paragraph (and never exposes raw JSON when the model is down).
            "summary": f"{len(results_data)} specialist{'s' if len(results_data) != 1 else ''} meet every requirement.",
        }

    async def _handle_summarize(
        self, query: str, entities: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        """Handle summarization queries."""
        crew_name = entities.get("crew_name")
        if not crew_name:
            return {
                "intent": "summarize",
                "query": query,
                "summary": "Please specify a crew member name to summarize.",
            }

        stmt = (
            select(CrewMemberModel)
            .where(CrewMemberModel.publication_status == "approved")
            .where(_contractor_account_condition())
            .options(
                selectinload(CrewMemberModel.certifications),
                selectinload(CrewMemberModel.documents),
            )
            .where(CrewMemberModel.full_name.ilike(_contains_like(str(crew_name)), escape="\\"))
        )
        # A partial name can match several approved profiles (for example
        # "Alex Carter" and "Alex Carter Jr"). Do not let
        # scalar_one_or_none() turn that normal ambiguity into a 500, and do
        # not silently summarize an arbitrary person. Prefer one exact
        # case-insensitive match; otherwise require the caller to clarify.
        result = await db_session.execute(stmt.limit(2))
        matches = list(result.scalars().all())
        normalized_name = str(crew_name).strip().casefold()
        exact_matches = [
            candidate
            for candidate in matches
            if candidate.full_name.strip().casefold() == normalized_name
        ]
        if len(exact_matches) == 1:
            crew = exact_matches[0]
        elif len(matches) == 1:
            crew = matches[0]
        elif len(matches) > 1:
            return {
                "intent": "summarize",
                "query": query,
                "summary": "More than one approved specialist matches that name. Please be more specific.",
            }
        else:
            crew = None

        if not crew:
            return {
                "intent": "summarize",
                "query": query,
                "summary": f"No crew member found with name '{crew_name}'.",
            }

        summary = await self.generate_crew_summary(crew, query=query)

        return {
            "intent": "summarize",
            "query": query,
            "crew_id": crew.id,
            "crew_name": crew.full_name,
            "summary": summary,
        }

    async def generate_crew_summary(
        self, crew: CrewMemberModel, *, query: str | None = None
    ) -> str:
        """Build the crew_data/doc_data context and generate the narrative
        summary for an already-resolved crew member.

        Shared by the NL "summarize X" search path (_handle_summarize, which
        still needs a fuzzy name lookup to resolve `crew` in the first
        place) and the direct by-ID path
        (ConsultantKnowledgeService.summarize), which doesn't. `crew` must
        have certifications and documents eager-loaded.
        """
        crew_data = {
            "id": crew.id,
            "name": crew.full_name,
            "nationality": crew.nationality,
            "country_of_residence": crew.country_of_residence,
            "gender": crew.gender,
            "languages": crew.languages,
            "flying_point": crew.flying_point,
            "education": crew.education,
            "professional_summary": crew.professional_summary,
            "experience_years": _experience_years(crew.experience_months),
            "availability": crew.availability_status,
            "training_qualifications": crew.training_qualifications or [],
            "geographical_experience": crew.geographical_experience or [],
            "systems_experience": crew.systems_experience or [],
            "tags": crew.tags or [],
            "certifications": [
                {
                    "type": c.cert_type,
                    "expiry_date": str(c.expiry_date) if c.expiry_date else None,
                    "status": c.status,
                }
                for c in (crew.certifications or [])
            ],
        }

        # Document metadata and extraction payloads are C2/C3 data and may
        # reveal identity, medical, or passport information. The summary is a
        # T1 surface, so expose no document metadata to the model.
        doc_data = "Document contents are not included in this summary."

        return await self._generate_response(
            "summarize_response",
            query or f"Summarize {crew.full_name}",
            json.dumps(crew_data, indent=2),
            prose=True,
            document_data=doc_data,
        )

    async def _handle_compliance(
        self, query: str, entities: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        """Handle compliance queries."""
        today = date.today()
        threshold = today + timedelta(days=90)

        stmt = (
            select(CrewMemberModel)
            .where(CrewMemberModel.publication_status == "approved")
            .where(_contractor_account_condition())
            .options(selectinload(CrewMemberModel.certifications))
            .join(CertificationModel)
            .where(
                or_(
                    CertificationModel.expiry_date < today,
                    and_(
                        CertificationModel.expiry_date >= today,
                        CertificationModel.expiry_date <= threshold,
                    ),
                    and_(
                        CertificationModel.expiry_date.is_(None),
                        CertificationModel.status.in_(("expired", "expiring_soon")),
                    ),
                ),
                CertificationModel.verification_status == "verified",
                _not_explicitly_rejected(CertificationModel.status),
            )
        )

        # Compliance search is staff-only, but it is still an externally
        # triggerable query. Keep a pathological number of matching profiles
        # from becoming an unbounded ORM result and LLM prompt.
        result = await db_session.execute(stmt.limit(100))
        crew_list = result.scalars().unique().all()

        compliance_data = []
        for crew in crew_list:
            expired_certs = []
            expiring_certs = []
            for cert in crew.certifications:
                compliance_status = _derived_compliance_status(cert.expiry_date, cert.status, today)
                if compliance_status is None or cert.verification_status == "rejected":
                    continue
                if cert.expiry_date:
                    if compliance_status == "expired":
                        expired_certs.append(
                            {
                                "type": cert.cert_type,
                                "expiry": str(cert.expiry_date),
                                "status": "expired",
                            }
                        )
                    elif compliance_status == "expiring_soon":
                        expiring_certs.append(
                            {
                                "type": cert.cert_type,
                                "expiry": str(cert.expiry_date),
                                "status": "expiring_soon",
                            }
                        )
                elif cert.status == "expired":
                    expired_certs.append(
                        {
                            "type": cert.cert_type,
                            "expiry": "unknown",
                            "status": "expired",
                        }
                    )
                elif cert.status == "expiring_soon":
                    expiring_certs.append(
                        {
                            "type": cert.cert_type,
                            "expiry": "unknown",
                            "status": "expiring_soon",
                        }
                    )

            if expired_certs or expiring_certs:
                compliance_data.append(
                    {
                        "id": crew.id,
                        "name": crew.full_name,
                        "expired": expired_certs,
                        "expiring_soon": expiring_certs,
                    }
                )

        summary = await self._generate_response(
            "compliance_response", query, json.dumps(compliance_data, indent=2)
        )

        return {
            "intent": "compliance",
            "query": query,
            "results": compliance_data,
            "summary": summary,
            "total_issues": len(compliance_data),
        }

    async def _handle_matching(
        self, query: str, entities: dict[str, Any], db_session: AsyncSession
    ) -> dict[str, Any]:
        """Handle recruiter matching with every stated requirement enforced.

        Matching used to have a second, certification-only SQL path. It lost
        nationality, skills and location constraints and could return a
        plausible-looking but unrelated contractor. Reuse the audited search
        implementation so both interfaces have identical semantics.
        """
        response = await self._handle_search(query, entities, db_session)
        response["intent"] = "matching"
        return response

    async def _handle_general(self, query: str, db_session: AsyncSession) -> dict[str, Any]:
        """Handle general queries."""
        return {
            "intent": "general",
            "query": query,
            "summary": "I can help you search crew members, summarize profiles, check compliance, or match candidates to projects. What would you like to know?",
        }

    async def _generate_response(
        self, prompt_key: str, query: str, results: str, *, prose: bool = False, **kwargs: Any
    ) -> str:
        """Generate LLM response for the given prompt type.

        prose=True (used by summarize_response) asks Ollama for
        unconstrained text instead of its default JSON-decoding mode —
        with JSON mode on, a narrative-prose prompt still gets valid JSON
        back, just prose wrapped in an object like {"profile": "..."}, so
        the raw-JSON-passthrough branch below is skipped for prose too.
        """
        prompt_template = CREW_QUERY_PROMPTS.get(prompt_key, "")
        if not prompt_template:
            return results

        try:
            prompt = prompt_template.format(query=query, results=results, **kwargs)
            result = await ollama_client.extract(prompt, json_format=not prose)
            response = result.get("response", results)
            if not isinstance(response, str):
                logger.warning("Ollama returned a non-string response field; using fallback")
                return results
            if len(response) > MAX_GENERATED_RESPONSE_LENGTH:
                logger.warning("Ollama response exceeded the bounded output length")
                return results if not prose else response[:MAX_GENERATED_RESPONSE_LENGTH]
            if prose:
                return response.strip()
            try:
                json.loads(response)
                return response
            except (json.JSONDecodeError, TypeError):
                return response.strip()
        except Exception as e:
            logger.error("Response generation failed: %s", type(e).__name__)
            return results


crew_query_service = CrewQueryService()
