from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from app.domain.fields import normalize_classification
from app.services.ollama import ollama_client

logger = logging.getLogger(__name__)

CONFIDENCE_AUTO_ACCEPT = 0.85
CONFIDENCE_REVIEW_THRESHOLD = 0.50

# Vision payload guard: base64 inflates raw bytes by ~33% before they enter
# the LLM request, so cap source images well below the 50 MB upload limit.
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_EXTRACTION_RESPONSE_LENGTH = 100_000
MAX_EXTRACTED_STRING_LENGTH = 10_000
MAX_EXTRACTED_LIST_ITEMS = 100
MAX_EXTRACTED_OBJECT_FIELDS = 100

EXTRACTION_FIELDS = frozenset(
    {
        "document_type",
        "certificate_type",
        "certificate_number",
        "issuing_body",
        "holder_name",
        "issue_date",
        "expiry_date",
        "renewal_date",
        "training_provider",
        "certification_level",
        "confidence",
        "needs_review",
        "document_mismatch",
        "notes",
        "classification",
        "reasoning",
        "language",
        "full_name",
        "email",
        "phone",
        "nationality",
        "country_of_residence",
        "date_of_birth",
        "gender",
        "flying_point",
        "address",
        "qualifications",
        "skills",
        "expertise",
        "systems",
        "training_qualifications",
        "certifications",
        "specializations",
        "work_history",
        "languages",
        "total_years_experience",
        "certification_expiry_dates",
        "certification_issue_dates",
        "id_type",
        "document_number",
        "issuing_authority",
        "visa_type",
        "client_name",
        "project_name",
        "project_type",
        "location",
        "country",
        "start_date",
        "end_date",
        "personnel",
        "requirements",
        "status",
        "crew_member_name",
        "evaluation_date",
        "rating",
        "competencies",
        "strengths",
        "areas_for_improvement",
        "recommend_for_future",
        "form_type",
        "insurance_provider",
        "insurance_policy_number",
        "insurance_expiry",
        "medical_status",
        "next_of_kin_name",
        "next_of_kin_phone",
        "error",
    }
)

EXTRACTION_PROMPTS = {
    "certificate": """You are extracting structured data from a training certificate or certification document.

Extract the following information and return it as JSON:
{{
  "document_type": "certificate",
  "certificate_type": "One of: BOSIET, STCW, MMO, PAM, NEBOSH, OFFSHORE_MEDICAL, HSE, OPITO, OTHER",
  "certificate_number": "The certificate ID or number",
  "issuing_body": "Organization that issued the certificate",
  "holder_name": "Full name of the person this certificate belongs to",
  "issue_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "renewal_date": "YYYY-MM-DD or null",
  "training_provider": "Company that delivered the training, if different from issuing body",
  "certification_level": "Level or grade if mentioned",
  "confidence": {{
    "certificate_type": 0.0-1.0,
    "certificate_number": 0.0-1.0,
    "issuing_body": 0.0-1.0,
    "holder_name": 0.0-1.0,
    "issue_date": 0.0-1.0,
    "expiry_date": 0.0-1.0
  }},
  "needs_review": ["field_names_that_are_uncertain"],
  "document_mismatch": false,
  "notes": "Any issues or observations"
}}

IMPORTANT: Pay special attention to expiry dates. If unclear, set confidence below 0.5.

Document to analyze:
{document_text}""",
    "cv": """You are extracting structured data from a CV or resume for an energy industry consultant.

The document may have sections like: PERSONAL INFORMATION, PROFESSIONAL SUMMARY, EXPERTISE, GEOGRAPHICAL EXPERIENCE, RECENT PROJECTS, CERTIFICATIONS, TRAINING/QUALIFICATIONS, SYSTEMS EXPERIENCE.

Return JSON:
{{
  "document_type": "cv",
  "full_name": "Person's full name",
  "email": "Email address or null",
  "phone": "Phone number or null",
  "nationality": "Nationality if stated, or null",
  "country_of_residence": "Country of residence if stated, or null",
  "date_of_birth": "YYYY-MM-DD or null (preserve original DD/MM/YYYY if the CV uses it, normalised to ISO if possible)",
  "gender": "Gender if stated, or null",
  "flying_point": "Nearest international airport or departure hub if stated, or null",
  "address": "Location/city if stated, or null",
  "qualifications": [{{"degree": "", "field": "", "institution": "", "year": ""}}],
  "skills": ["skill_1", "skill_2"],
  "expertise": ["items listed under the CV's explicit EXPERTISE section, preserving the wording and order"],
  "systems": ["software, equipment, and operational systems explicitly named in the CV"],
  "training_qualifications": ["ONLY the rows listed under the explicit TRAINING/QUALIFICATIONS (or TRAINING, CERTIFICATIONS, CERTIFICATES) section of the CV. Preserve the wording of the course/certificate name, the place, and any completion/expiry dates as a single string per row, e.g. 'FOET Further Offshore Emergency Training including HUET with CA EBS — Vulcan Training — Completed 18/12/2025 — Expires 01/02/2030'. Do NOT include training-related skills mentioned elsewhere (e.g. a JNCC mention inside a Skills & Competencies list is NOT a training entry)."],
  "certifications": ["cert_name_1", "cert_name_2 — also extract any named ticket/certificate/safety course found in a TRAINING/QUALIFICATIONS or CERTIFICATIONS section, such as BOSIET, FOET, CA-EBS, OGUK Medical, GWO, STCW, MIST, H2S, HUET. Use the canonical short name as it appears in the CV."],
  "specializations": ["MMO", "PAM", "QC", "HSE", "Geophysicist", "Environmental", "PSO", "Observer"],
  "work_history": [{{"client": "", "project": "", "project_type": "", "location": "", "country": "", "role": "", "start_date": "", "end_date": "", "responsibilities": ""}}],
  "languages": ["language_1", "language_2"],  // each entry should be the language name (e.g. "Polish", "English"), optionally followed by proficiency in parentheses (e.g. "English (fluent)"); strip conversational prefixes like "native:", "spoken:"
  "total_years_experience": "Number or null",
  "certification_expiry_dates": {{"BOSIET": "2030-02-01", "FOET": "2030-02-01"}},
  "certification_issue_dates": {{"BOSIET": "2019-02-01", "FOET": "2019-02-01"}},
  "confidence": {{"full_name": 0.0-1.0, "email": 0.0-1.0, "work_history": 0.0-1.0, "specializations": 0.0-1.0, "skills": 0.0-1.0, "expertise": 0.0-1.0, "certifications": 0.0-1.0}},
  "needs_review": [],
  "document_mismatch": false,
  "notes": ""
}}

Specialization identification guide:
- MMO: Marine Mammal Observer
- PAM: Passive Acoustic Monitoring
- QC: Quality Control
- HSE: Health, Safety, Environment
- PSO: Protected Species Observer
- Environmental: Environmental compliance, surveying

For work_history dates, if only years are given use YYYY-01-01. If a role is ongoing set end_date to null.

Document to analyze:
{document_text}""",
    "identity": """You are extracting structured data from an identity document (passport, visa, or work permit).

Return JSON:
{{
  "document_type": "identity",
  "id_type": "passport, visa, work_permit, national_id, or other",
  "document_number": "ID/passport number",
  "full_name": "Full name as shown on document",
  "nationality": "Nationality or issuing country",
  "date_of_birth": "YYYY-MM-DD or null",
  "issue_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "issuing_authority": "Authority that issued the document",
  "visa_type": "Type of visa if applicable",
  "confidence": {{"document_number": 0.0-1.0, "full_name": 0.0-1.0, "expiry_date": 0.0-1.0}},
  "needs_review": [],
  "document_mismatch": false,
  "notes": ""
}}

Document to analyze:
{document_text}""",
    "project": """You are extracting structured data from a project-related document.

Return JSON:
{{
  "document_type": "project",
  "client_name": "Client or oil company name",
  "project_name": "Project name or description",
  "project_type": "marine_seismic, land_seismic, offshore_wind, environmental, or other",
  "location": "Survey or project location",
  "country": "Country",
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "personnel": [{{"name": "", "role": ""}}],
  "requirements": ["Required certification or skill"],
  "status": "planned, active, completed, or unknown",
  "confidence": {{"client_name": 0.0-1.0, "project_name": 0.0-1.0, "location": 0.0-1.0}},
  "needs_review": [],
  "document_mismatch": false,
  "notes": ""
}}

Document to analyze:
{document_text}""",
    "performance": """You are extracting structured data from a performance review or client feedback form.

Return JSON:
{{
  "document_type": "performance",
  "crew_member_name": "Name of the person being evaluated",
  "client_name": "Client or company name",
  "project_name": "Project name or null",
  "evaluation_date": "YYYY-MM-DD or null",
  "rating": "Numerical rating if given or null",
  "competencies": [{{"competency": "", "rating": "", "comments": ""}}],
  "strengths": ["strength_1"],
  "areas_for_improvement": ["area_1"],
  "recommend_for_future": true/false/null,
  "confidence": {{"crew_member_name": 0.0-1.0, "client_name": 0.0-1.0, "rating": 0.0-1.0}},
  "needs_review": [],
  "document_mismatch": false,
  "notes": ""
}}

Document to analyze:
{document_text}""",
    "compliance": """You are extracting structured data from a compliance, insurance, or medical declaration form.

Return JSON:
{{
  "document_type": "compliance",
  "form_type": "insurance, medical_declaration, next_of_kin, emergency_contact, or other",
  "full_name": "Person's full name",
  "date_of_birth": "YYYY-MM-DD or null",
  "nationality": "Nationality or null",
  "insurance_provider": "Insurance company name or null",
  "insurance_policy_number": "Policy number or null",
  "insurance_expiry": "YYYY-MM-DD or null",
  "medical_status": "fit, fit_with_restrictions, unfit, or null",
  "next_of_kin_name": "Emergency contact name or null",
  "next_of_kin_phone": "Phone number or null",
  "confidence": {{"full_name": 0.0-1.0, "insurance_policy_number": 0.0-1.0, "medical_status": 0.0-1.0}},
  "needs_review": [],
  "document_mismatch": false,
  "notes": ""
}}

Document to analyze:
{document_text}""",
    "classification": """Classify the following document into one of these categories:
- certificate: Training certificates, safety certs, medical certs
- cv: Resume, CV, curriculum vitae
- identity: Passport, visa, work permit, ID card
- project: Project specs, assignment emails, survey reports
- performance: Performance reviews, client feedback, evaluations
- compliance: Insurance forms, medical declarations, next of kin forms
- other: Anything not matching the above

Return JSON:
{{
  "classification": "one of the categories above",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation",
  "language": "Primary language of the document"
}}

Document to analyze:
{document_text}""",
}


class ExtractionService:
    """Service for extracting structured data from documents using LLM."""

    async def classify_document(self, text: str) -> dict[str, Any]:
        """Classify a document type."""
        prompt = EXTRACTION_PROMPTS["classification"].format(document_text=text[:4000])
        result = await ollama_client.extract(prompt)
        return self.parse_response(result)

    def classify_document_sync(self, text: str) -> dict[str, Any]:
        """Classify a document type (sync version for Celery)."""
        prompt = EXTRACTION_PROMPTS["classification"].format(document_text=text[:4000])
        result = ollama_client.extract_sync(prompt)
        return self.parse_response(result)

    @staticmethod
    def classification_from_result(result: dict[str, Any]) -> str:
        """Return a safe classification value from untrusted model output."""
        value = result.get("classification")
        return value if isinstance(value, str) else "other"

    @staticmethod
    def confidence_from_result(result: dict[str, Any]) -> dict[str, Any]:
        """Return dictionary-shaped confidence data for JSON persistence."""
        value = result.get("confidence")
        return value if isinstance(value, dict) else {}

    async def extract_document(
        self,
        text: str,
        document_type: str,
        is_image: bool = False,
    ) -> dict[str, Any]:
        """Extract structured data from a document."""
        normalized_type = normalize_classification(document_type)
        prompt_template = EXTRACTION_PROMPTS.get(normalized_type)
        if not prompt_template:
            raise ValueError(f"Unknown document type: {document_type}")

        prompt = prompt_template.format(document_text=text[:16000])
        model = ollama_client.vision_model if is_image else None
        result = await ollama_client.extract(prompt, model=model)
        return self.parse_response(result)

    def extract_document_sync(
        self,
        text: str,
        document_type: str,
        is_image: bool = False,
    ) -> dict[str, Any]:
        """Extract structured data from a document (sync version for Celery)."""
        normalized_type = normalize_classification(document_type)
        prompt_template = EXTRACTION_PROMPTS.get(normalized_type)
        if not prompt_template:
            raise ValueError(f"Unknown document type: {document_type}")

        prompt = prompt_template.format(document_text=text[:16000])
        model = ollama_client.vision_model if is_image else None
        result = ollama_client.extract_sync(prompt, model=model)
        return self.parse_response(result)

    async def extract_from_image(
        self,
        image_path: str,
        document_type: str,
    ) -> dict[str, Any]:
        """Extract data from image using vision model (async version)."""
        import base64
        import os

        # Bound the payload before reading: base64 inflates bytes by ~33%,
        # and an uncapped image becomes an OOM-sized LLM request.
        if os.path.getsize(image_path) > MAX_IMAGE_BYTES:
            raise ValueError(
                f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB cap for vision extraction"
            )
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        normalized_type = normalize_classification(document_type)
        prompt_template = EXTRACTION_PROMPTS.get(normalized_type, EXTRACTION_PROMPTS["certificate"])
        # Document text placeholder not needed for image; prompt already contains instructions
        prompt = prompt_template.format(document_text="[IMAGE]")
        result = await ollama_client.extract(
            prompt, model=ollama_client.vision_model, images=[image_data]
        )
        return self.parse_response(result)

    def extract_from_image_sync(
        self,
        image_path: str,
        document_type: str,
    ) -> dict[str, Any]:
        """Extract data from image using vision model (sync version)."""
        import base64
        import os

        if os.path.getsize(image_path) > MAX_IMAGE_BYTES:
            raise ValueError(
                f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB cap for vision extraction"
            )
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        normalized_type = normalize_classification(document_type)
        prompt = EXTRACTION_PROMPTS.get(normalized_type, EXTRACTION_PROMPTS["certificate"])
        # Format prompt to keep placeholder for consistency, but image data carries content
        try:
            prompt = prompt.format(document_text="[IMAGE]")
        except Exception as e:
            logger.warning(
                "Vision prompt formatting failed, using raw template: %s",
                type(e).__name__,
            )
        result = ollama_client.extract_sync(
            prompt, model=ollama_client.vision_model, images=[image_data]
        )
        return self.parse_response(result)

    def determine_review_status(
        self,
        extracted_data: dict[str, Any],
    ) -> tuple[str, list[str]]:
        """Determine if extraction needs human review based on confidence."""
        # The model decides the shape of its own output: "confidence" comes back
        # as a per-field mapping most of the time, but sometimes as a bare
        # summary string ("high").  Anything that is not a mapping carries no
        # per-field signal, so treat it as absent rather than letting .items()
        # raise and fail the whole extraction.
        confidence = extracted_data.get("confidence")
        if confidence is None:
            confidence = {}
        elif not isinstance(confidence, dict):
            return "needs_review", ["confidence"]
        needs_review = []
        malformed_confidence_fields = []

        for field, score in confidence.items():
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))
                or not 0.0 <= float(score) <= 1.0
            ):
                malformed_confidence_fields.append(field)
            elif score < CONFIDENCE_REVIEW_THRESHOLD:
                needs_review.append(field)

        if malformed_confidence_fields:
            return "needs_review", malformed_confidence_fields

        if needs_review:
            return "needs_review", needs_review

        low_confidence_fields = [
            f
            for f, s in confidence.items()
            if isinstance(s, (int, float))
            and not isinstance(s, bool)
            and s < CONFIDENCE_AUTO_ACCEPT
        ]

        if low_confidence_fields:
            return "extracted", low_confidence_fields

        return "extracted", []

    @staticmethod
    def parse_response(result: dict[str, Any]) -> dict[str, Any]:
        """Parse and validate LLM response."""
        response_text = result.get("response", "")

        if not isinstance(response_text, str) or not response_text.strip():
            return {"error": "Empty response from LLM", "needs_review": ["all"]}
        if len(response_text) > MAX_EXTRACTION_RESPONSE_LENGTH:
            return {"error": "LLM response is too large", "needs_review": ["all"]}

        try:
            data = ExtractionService._load_json_response(response_text)
            return ExtractionService._normalize_extracted_payload(data)
        except (json.JSONDecodeError, ValueError):
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1:
                try:
                    data = ExtractionService._load_json_response(response_text[start : end + 1])
                    return ExtractionService._normalize_extracted_payload(data)
                except (json.JSONDecodeError, ValueError):
                    pass

            return {
                "error": "Invalid JSON from LLM",
                "needs_review": ["all"],
            }

    @staticmethod
    def _load_json_response(response_text: str) -> Any:
        """Load strict JSON so non-standard numeric constants never reach persistence."""

        def reject_non_standard_number(value: str) -> None:
            raise ValueError(f"Non-standard JSON number: {value}")

        return json.loads(response_text, parse_constant=reject_non_standard_number)

    @staticmethod
    def _normalize_extracted_payload(data: Any) -> dict[str, Any]:
        """Normalize common extraction quirks so downstream code sees clean values."""
        if not isinstance(data, dict):
            return {
                "error": "LLM response must be a JSON object",
                "needs_review": ["all"],
            }
        data = {
            key: ExtractionService._bound_json_value(value)
            for key, value in data.items()
            if key in EXTRACTION_FIELDS
        }
        languages = data.get("languages")
        if isinstance(languages, list):
            normalized: list[str] = []
            for entry in languages:
                if not isinstance(entry, str):
                    continue
                text = entry.strip()
                if not text:
                    continue
                parts = [part.strip() for part in re.split(r",|;|/| and ", text) if part.strip()]
                for part in parts:
                    # Drop trailing proficiency descriptors like "(native)" / "(fluent)".
                    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", part).strip()
                    if cleaned:
                        normalized.append(cleaned)
            if normalized:
                data["languages"] = normalized
        return data

    @staticmethod
    def _bound_json_value(value: Any, depth: int = 0) -> Any:
        """Bound nested model output before it is persisted as extraction data."""
        if depth >= 3:
            return None
        if isinstance(value, str):
            return value[:MAX_EXTRACTED_STRING_LENGTH]
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, list):
            return [
                ExtractionService._bound_json_value(item, depth + 1)
                for item in value[:MAX_EXTRACTED_LIST_ITEMS]
            ]
        if isinstance(value, dict):
            return {
                key: ExtractionService._bound_json_value(item, depth + 1)
                for key, item in list(value.items())[:MAX_EXTRACTED_OBJECT_FIELDS]
                if isinstance(key, str)
            }
        return value


extraction_service = ExtractionService()
