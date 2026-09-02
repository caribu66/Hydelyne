from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from difflib import get_close_matches
from typing import Any

import sqlalchemy as sa
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.domain.certifications import CERT_ALIASES, CERT_FAMILIES, normalize_cert_name
from app.models import Certification as CertificationModel
from app.models import CrewMember as CrewMemberModel
from app.models import WorkHistory as WorkHistoryModel
from app.services.ollama import ollama_client

logger = logging.getLogger(__name__)

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
# unsafe "best guess" correction of a person’s name or a compliance document.
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

    async def process_query(self, query: str, db_session) -> dict[str, Any]:
        """Process a natural language query about crew members."""
        intent_result = await self._classify_intent(query)
        intent = intent_result.get("intent", "general")
        entities = intent_result.get("entities", {})

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
            classified = json.loads(response_text)
            if not isinstance(classified, dict):
                raise ValueError("Intent classifier returned a non-object response")
            return self._apply_deterministic_query_rules(query, classified)
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            # Search remains useful when the local model is unavailable.
            return self._apply_deterministic_query_rules(
                query, {"intent": "search", "entities": {}, "confidence": 0.0}
            )

    @staticmethod
    def _apply_deterministic_query_rules(query: str, classified: dict[str, Any]) -> dict[str, Any]:
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
            if (
                " " not in alias
                and alias in lower_query
                and certificate not in inferred_certifications
            ):
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

    async def _handle_search(self, query: str, entities: dict, db_session) -> dict[str, Any]:
        """Handle search/filter queries with broad matching across crew data."""
        stmt = select(CrewMemberModel).options(
            selectinload(CrewMemberModel.certifications),
            selectinload(CrewMemberModel.work_history),
        )

        filters = []
        search_terms = []

        # Source systems may represent a medical as a certification or as a
        # dedicated crew field, so include both representations.
        if entities.get("medical_required"):
            if entities.get("medical_valid"):
                filters.append(
                    or_(
                        and_(
                            CrewMemberModel.medical_status.in_(("fit", "fit_with_restrictions")),
                            CrewMemberModel.medical_expiry.is_not(None),
                            CrewMemberModel.medical_expiry >= date.today(),
                        ),
                        CrewMemberModel.certifications.any(
                            and_(
                                CertificationModel.cert_type.ilike("%medical%"),
                                CertificationModel.status.in_(("valid", "pending_verification")),
                                or_(
                                    CertificationModel.expiry_date.is_(None),
                                    CertificationModel.expiry_date >= date.today(),
                                ),
                            )
                        ),
                    )
                )
            else:
                filters.append(
                    or_(
                        CrewMemberModel.certifications.any(
                            CertificationModel.cert_type.ilike("%medical%")
                        ),
                        CrewMemberModel.medical_status.is_not(None),
                        CrewMemberModel.medical_expiry.is_not(None),
                        CrewMemberModel.medical_provider.is_not(None),
                    )
                )

        if entities.get("nationality"):
            filters.append(CrewMemberModel.nationality.ilike(f"%{entities['nationality']}%"))

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
            filters.append(
                CrewMemberModel.certifications.any(
                    CertificationModel.cert_type.ilike(f"%{keyword}%")
                )
            )

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
                filters.append(
                    CrewMemberModel.certifications.any(CertificationModel.cert_type == cert_type)
                )

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

        # Broad text search across multiple fields
        if search_terms:
            term_filters = []
            for term in search_terms:
                term_filters.append(CrewMemberModel.full_name.ilike(f"%{term}%"))
                term_filters.append(sa.cast(CrewMemberModel.tags, sa.String).ilike(f"%{term}%"))
                term_filters.append(CrewMemberModel.internal_notes.ilike(f"%{term}%"))
                # Work history fields
                term_filters.append(
                    CrewMemberModel.work_history.any(
                        or_(
                            WorkHistoryModel.project_type.ilike(f"%{term}%"),
                            WorkHistoryModel.location.ilike(f"%{term}%"),
                            WorkHistoryModel.responsibilities.ilike(f"%{term}%"),
                            WorkHistoryModel.role.ilike(f"%{term}%"),
                            WorkHistoryModel.client_name.ilike(f"%{term}%"),
                        )
                    )
                )
                # Certification type names
                term_filters.append(
                    CrewMemberModel.certifications.any(
                        CertificationModel.cert_type.ilike(f"%{term}%")
                    )
                )
                # Also split multi-word terms for partial matching
                words = term.split()
                if len(words) > 1:
                    for word in words:
                        if len(word) > 3:  # Skip short words
                            term_filters.append(
                                CrewMemberModel.certifications.any(
                                    CertificationModel.cert_type.ilike(f"%{word}%")
                                )
                            )
                            term_filters.append(
                                sa.cast(CrewMemberModel.tags, sa.String).ilike(f"%{word}%")
                            )
            filters.append(or_(*term_filters))

        if filters:
            stmt = stmt.where(and_(*filters))

        result = await db_session.execute(stmt.limit(20))
        crew_list = result.scalars().unique().all()

        # Once every hard requirement is met, rank deterministically on the
        # information agents actually care about: ready to mobilize first,
        # then the most audited experience. Never let incidental keyword hits
        # decide the top candidate.
        crew_list.sort(
            key=lambda crew: (
                crew.availability_status == "available",
                crew.experience_months or 0,
                crew.profile_completeness_score or 0,
            ),
            reverse=True,
        )

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
                    "email": crew.email,
                    "availability": crew.availability_status,
                    "experience_years": round((crew.experience_months or 0) / 12, 1),
                    "nationality": crew.nationality,
                    "country_of_residence": crew.country_of_residence,
                    "languages": crew.languages or [],
                    "flying_point": crew.flying_point,
                    "education": crew.education,
                    "tags": crew.tags or [],
                    "training_qualifications": crew.training_qualifications or [],
                    "geographical_experience": crew.geographical_experience or [],
                    "systems_experience": crew.systems_experience or [],
                    "certifications": [c.cert_type for c in crew.certifications]
                    if crew.certifications
                    else [],
                    "work_locations": list(
                        set(wh.location for wh in crew.work_history if wh.location)
                    )
                    if crew.work_history
                    else [],
                    "work_countries": list(
                        set(wh.country for wh in crew.work_history if wh.country)
                    )
                    if crew.work_history
                    else [],
                    "project_types": list(
                        set(wh.project_type for wh in crew.work_history if wh.project_type)
                    )
                    if crew.work_history
                    else [],
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

    async def _handle_summarize(self, query: str, entities: dict, db_session) -> dict[str, Any]:
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
            .options(
                selectinload(CrewMemberModel.certifications),
                selectinload(CrewMemberModel.documents),
            )
            .where(CrewMemberModel.full_name.ilike(f"%{crew_name}%"))
        )
        result = await db_session.execute(stmt)
        crew = result.scalar_one_or_none()

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
        have certifications, work_history, and documents eager-loaded.
        """
        crew_data = {
            "id": crew.id,
            "name": crew.full_name,
            "email": crew.email,
            "phone": crew.phone,
            "nationality": crew.nationality,
            "country_of_residence": crew.country_of_residence,
            "date_of_birth": str(crew.date_of_birth) if crew.date_of_birth else None,
            "gender": crew.gender,
            "languages": crew.languages,
            "flying_point": crew.flying_point,
            "education": crew.education,
            "professional_summary": crew.professional_summary,
            "experience_years": round((crew.experience_months or 0) / 12, 1),
            "availability": crew.availability_status,
            "passport_expiry": str(crew.passport_expiry) if crew.passport_expiry else None,
            "medical_expiry": str(crew.medical_expiry) if crew.medical_expiry else None,
            "medical_status": crew.medical_status,
            "training_qualifications": crew.training_qualifications or [],
            "geographical_experience": crew.geographical_experience or [],
            "systems_experience": crew.systems_experience or [],
            "tags": crew.tags or [],
            "certifications": [
                {
                    "type": c.cert_type,
                    "issuing_body": c.issuing_body,
                    "issue_date": str(c.issue_date) if c.issue_date else None,
                    "expiry_date": str(c.expiry_date) if c.expiry_date else None,
                    "status": c.status,
                }
                for c in (crew.certifications or [])
            ],
            "work_history": [
                {
                    "client": wh.client_name,
                    "country": wh.country,
                    "project_type": wh.project_type,
                    "role": wh.role,
                    "start_date": str(wh.start_date) if wh.start_date else None,
                }
                for wh in (crew.work_history or [])
            ],
        }

        doc_data = []
        for doc in crew.documents:
            if doc.extracted_data:
                doc_data.append(
                    {
                        "file": doc.file_name,
                        "classification": doc.classification,
                        "data": doc.extracted_data,
                    }
                )

        return await self._generate_response(
            "summarize_response",
            query or f"Summarize {crew.full_name}",
            json.dumps(crew_data, indent=2),
            prose=True,
            document_data=json.dumps(doc_data, indent=2) if doc_data else "No documents",
        )

    async def _handle_compliance(self, query: str, entities: dict, db_session) -> dict[str, Any]:
        """Handle compliance queries."""
        today = date.today()
        threshold = today + timedelta(days=90)

        stmt = (
            select(CrewMemberModel)
            .options(selectinload(CrewMemberModel.certifications))
            .join(CertificationModel)
            .where(
                or_(
                    CertificationModel.status == "expired",
                    CertificationModel.status == "expiring_soon",
                )
            )
        )

        result = await db_session.execute(stmt)
        crew_list = result.scalars().unique().all()

        compliance_data = []
        for crew in crew_list:
            expired_certs = []
            expiring_certs = []
            for cert in crew.certifications:
                if cert.expiry_date:
                    if cert.expiry_date < today:
                        expired_certs.append(
                            {
                                "type": cert.cert_type,
                                "expiry": str(cert.expiry_date),
                                "status": "expired",
                            }
                        )
                    elif cert.expiry_date <= threshold:
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

    async def _handle_matching(self, query: str, entities: dict, db_session) -> dict[str, Any]:
        """Handle recruiter matching with every stated requirement enforced.

        Matching used to have a second, certification-only SQL path. It lost
        nationality, skills and location constraints and could return a
        plausible-looking but unrelated contractor. Reuse the audited search
        implementation so both interfaces have identical semantics.
        """
        response = await self._handle_search(query, entities, db_session)
        response["intent"] = "matching"
        return response

    async def _handle_general(self, query: str, db_session) -> dict[str, Any]:
        """Handle general queries."""
        return {
            "intent": "general",
            "query": query,
            "summary": "I can help you search crew members, summarize profiles, check compliance, or match candidates to projects. What would you like to know?",
        }

    async def _generate_response(
        self, prompt_key: str, query: str, results: str, *, prose: bool = False, **kwargs
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
            if prose:
                return response.strip()
            try:
                json.loads(response)
                return response
            except (json.JSONDecodeError, TypeError):
                return response.strip()
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return results


crew_query_service = CrewQueryService()
