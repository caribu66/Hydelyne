"""Service to process extracted CV data and populate crew member profile."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_session_factory
from app.domain.certifications import CERT_ALIASES
from app.models import Certification, CrewMember, WorkHistory

logger = logging.getLogger(__name__)


class CVProcessingService:
    """Process extracted CV data and populate crew member records."""

    async def process_cv_extraction(
        self,
        crew_member_id: str,
        extracted_data: dict[str, Any],
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """Process extracted CV data and update crew member profile.

        Returns summary of what was created/updated.
        """
        factory = get_session_factory()
        result_summary = {
            "certifications_created": 0,
            "work_history_created": 0,
            "fields_updated": [],
        }

        async with factory() as session:
            crew = await session.execute(
                select(CrewMember)
                .options(
                    selectinload(CrewMember.certifications),
                    selectinload(CrewMember.work_history),
                )
                .where(CrewMember.id == crew_member_id)
            )
            crew_member = crew.scalar_one_or_none()

            if not crew_member:
                logger.error(f"Crew member {crew_member_id} not found")
                return {"error": "Crew member not found"}

            self._update_crew_fields(crew_member, extracted_data, result_summary)
            await self._create_certifications(
                session, crew_member, extracted_data, document_id, result_summary
            )
            await self._create_work_history(
                session, crew_member, extracted_data, document_id, result_summary
            )

            crew_member.profile_completeness_score = self._calculate_completeness(crew_member)
            await session.commit()

        from app.services.cache import cache_service

        # A newly-processed or re-processed CV changes the exact data an AI
        # summary would describe — a stale cached one would show outdated facts.
        await cache_service.delete(cache_service._make_key("summary", crew_member_id))

        return result_summary

    def _update_crew_fields(
        self,
        crew_member: CrewMember,
        data: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """Update crew member basic fields from extracted data."""
        # A CV-only import creates a deliberately recognisable placeholder.
        # Replace it only with a name actually extracted from the CV; never
        # overwrite a name an operator already supplied.
        if data.get("full_name") and crew_member.full_name.strip().lower() == "pending cv import":
            crew_member.full_name = data["full_name"]
            summary["fields_updated"].append("full_name")

        if data.get("email") and not crew_member.email:
            crew_member.email = data["email"]
            summary["fields_updated"].append("email")

        if data.get("phone") and not crew_member.phone:
            crew_member.phone = data["phone"]
            summary["fields_updated"].append("phone")

        if data.get("nationality") and not crew_member.nationality:
            crew_member.nationality = data["nationality"]
            summary["fields_updated"].append("nationality")

        if data.get("country_of_residence") and not crew_member.country_of_residence:
            crew_member.country_of_residence = data["country_of_residence"]
            summary["fields_updated"].append("country_of_residence")

        if data.get("gender") and not crew_member.gender:
            crew_member.gender = data["gender"]
            summary["fields_updated"].append("gender")

        if data.get("flying_point") and not crew_member.flying_point:
            crew_member.flying_point = data["flying_point"]
            summary["fields_updated"].append("flying_point")

        languages = data.get("languages")
        if languages and not crew_member.languages:
            if isinstance(languages, list):
                crew_member.languages = [
                    str(item).strip() for item in languages if str(item).strip()
                ]
            elif isinstance(languages, str):
                crew_member.languages = [
                    item.strip() for item in re.split(r",|;", languages) if item.strip()
                ]
            if crew_member.languages:
                summary["fields_updated"].append("languages")

        if data.get("date_of_birth") and not crew_member.date_of_birth:
            parsed_dob = self._parse_date(data.get("date_of_birth"))
            if parsed_dob:
                crew_member.date_of_birth = parsed_dob
                summary["fields_updated"].append("date_of_birth")

        if data.get("address") and not crew_member.address:
            crew_member.address = data["address"]
            summary["fields_updated"].append("address")

        extracted_tags = self._cv_tags(data)
        if extracted_tags:
            existing_tags = crew_member.tags if isinstance(crew_member.tags, list) else []
            merged_tags = list(dict.fromkeys([*existing_tags, *extracted_tags]))
            if merged_tags != existing_tags:
                crew_member.tags = merged_tags
                summary["fields_updated"].append("skills")

        education = self._education_summary(data)
        if education and not crew_member.education:
            crew_member.education = education
            summary["fields_updated"].append("education")

        professional_summary = data.get("professional_summary")
        if professional_summary and not crew_member.professional_summary:
            crew_member.professional_summary = professional_summary
            summary["fields_updated"].append("professional_summary")

        experience_months = self._experience_months(data)
        if experience_months and (crew_member.experience_months or 0) < experience_months:
            crew_member.experience_months = experience_months
            summary["fields_updated"].append("experience")

        geography = self._geographical_experience(data)
        if geography:
            existing_geography = (
                crew_member.geographical_experience
                if isinstance(crew_member.geographical_experience, list)
                else []
            )
            merged_geography = list(dict.fromkeys([*existing_geography, *geography]))
            if merged_geography != existing_geography:
                crew_member.geographical_experience = merged_geography
                summary["fields_updated"].append("geographical_experience")

        systems = self._systems_experience(data)
        if systems:
            existing_systems = (
                crew_member.systems_experience
                if isinstance(crew_member.systems_experience, list)
                else []
            )
            merged_systems = list(dict.fromkeys([*existing_systems, *systems]))
            if merged_systems != existing_systems:
                crew_member.systems_experience = merged_systems
                summary["fields_updated"].append("systems_experience")

        training = self._training_qualifications(data)
        if training:
            existing_training = (
                crew_member.training_qualifications
                if isinstance(crew_member.training_qualifications, list)
                else []
            )
            merged_training = list(dict.fromkeys([*existing_training, *training]))
            if merged_training != existing_training:
                crew_member.training_qualifications = merged_training
                summary["fields_updated"].append("training_qualifications")

    @staticmethod
    def _cv_tags(data: dict[str, Any]) -> list[str]:
        """Return stable, display-safe skills from the structured CV result."""
        values: list[str] = []
        for key in ("expertise", "skills", "specializations", "certifications"):
            for value in data.get(key) or []:
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())
        return list(dict.fromkeys(values))

    @staticmethod
    def _education_summary(data: dict[str, Any]) -> str | None:
        qualifications = data.get("qualifications") or data.get("education")
        if isinstance(qualifications, str) and qualifications.strip():
            return qualifications.strip()
        if isinstance(qualifications, list):
            items: list[str] = []
            for item in qualifications:
                if isinstance(item, str) and item.strip():
                    items.append(item.strip())
                elif isinstance(item, dict):
                    parts = [
                        str(item.get(key)).strip()
                        for key in ("degree", "field", "institution", "year")
                        if item.get(key)
                    ]
                    if parts:
                        items.append(" — ".join(parts))
            return "; ".join(dict.fromkeys(items)) or None
        return None

    @classmethod
    def _experience_months(cls, data: dict[str, Any]) -> int | None:
        """Estimate experience from the recorded CV employment dates."""
        dates: list[date] = []
        for work in data.get("work_history") or []:
            if not isinstance(work, dict):
                continue
            for field in ("start_date", "end_date"):
                parsed = cls._parse_date(work.get(field))
                if parsed:
                    dates.append(parsed)
        if len(dates) < 2:
            return None
        first, last = min(dates), max(dates)
        months = max(0, (last.year - first.year) * 12 + last.month - first.month)
        return months or None

    @staticmethod
    def _geographical_experience(data: dict[str, Any]) -> list[str]:
        """Collect locations stated in CV work history, preserving source order."""
        locations: list[str] = []
        for work in data.get("work_history") or []:
            if not isinstance(work, dict):
                continue
            for field in ("country", "location"):
                value = work.get(field)
                if isinstance(value, str) and value.strip():
                    locations.append(value.strip())
        return list(dict.fromkeys(locations))

    @staticmethod
    def _systems_experience(data: dict[str, Any]) -> list[str]:
        """Collect explicit software/equipment/system names from a CV."""
        values = [
            value.strip()
            for value in (data.get("systems") or [])
            if isinstance(value, str) and value.strip()
        ]
        pattern = re.compile(
            r"\b(PAMGuard|ADD(?:\s+Lofitech)?|QGIS|Microsoft Office(?: Suite)?)\b", re.I
        )
        for value in data.get("skills") or []:
            if isinstance(value, str):
                match = pattern.search(value)
                if match:
                    values.append(match.group(1).strip())
        return list(dict.fromkeys(values))

    @staticmethod
    def _training_qualifications(data: dict[str, Any]) -> list[str]:
        values: list[str] = []
        qualifications = data.get("qualifications") or []
        if isinstance(qualifications, list):
            for item in qualifications:
                if isinstance(item, str) and item.strip():
                    values.append(item.strip())
                elif isinstance(item, dict):
                    parts = [
                        str(item.get(key)).strip()
                        for key in ("degree", "field", "institution", "year")
                        if item.get(key)
                    ]
                    if parts:
                        values.append(" — ".join(parts))
        for value in data.get("training_qualifications") or data.get("certifications") or []:
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        return list(dict.fromkeys(values))

    @staticmethod
    def training_from_text(text: str) -> list[str]:
        """Recover training-section lines when an extractor omits the field."""
        values: list[str] = []
        active = False
        for raw_line in text.splitlines():
            line = raw_line.strip(" \t-•")
            upper = line.upper()
            if (
                re.search(r"\b(TRAINING|QUALIFICATIONS|CERTIFICATIONS)\b", upper)
                and len(line) < 100
            ):
                active = True
                continue
            if active and line and re.fullmatch(r"[A-Z][A-Z /&-]{3,}", line):
                active = False
            if active and line and len(line) >= 3:
                values.append(line)
            if len(values) >= 50:
                break
        return list(dict.fromkeys(values))

    @staticmethod
    def merge_table_extraction(
        extracted: dict[str, Any],
        table_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge deterministic table-extracted data into an LLM result.

        Table extraction is authoritative for any field it populated: the
        LLM is asked to interpret scrambled text and frequently invents or
        drops rows in long training tables.  Narrative fields like
        ``skills`` and ``bio`` are left to the LLM.
        """
        merged = dict(extracted)
        for key, value in table_payload.items():
            if key == "personal_information":
                info = value
                for label, val in info.items():
                    if not val:
                        continue
                    if label.startswith("NATIONALITY"):
                        merged.setdefault("nationality", val)
                    elif "COUNTRY OF RESIDENCE" in label:
                        merged.setdefault("country_of_residence", val)
                    elif "DATE OF BIRTH" in label:
                        merged.setdefault("date_of_birth", val)
                    elif label.startswith("GENDER"):
                        merged.setdefault("gender", val)
                    elif label.startswith("LANGUAGES"):
                        existing_langs = merged.get("languages")
                        # Prefer the LLM's normalised list when available.
                        if not existing_langs:
                            if isinstance(val, list):
                                merged["languages"] = val
                            else:
                                merged["languages"] = [
                                    piece.strip()
                                    for piece in re.split(r",|;", val)
                                    if piece.strip()
                                ]
                    elif "FLYING POINT" in label:
                        merged.setdefault("flying_point", val)
                    elif label.startswith("EDUCATION"):
                        merged.setdefault("education", val)
            elif key == "training_qualifications":
                if value:
                    merged["training_qualifications"] = value
            elif key == "training_qualifications_structured":
                merged[key] = value
            elif key == "certifications":
                existing = list(merged.get("certifications") or [])
                merged["certifications"] = list(dict.fromkeys([*existing, *value]))
            elif key == "work_history":
                if value:
                    merged["work_history"] = value
            elif key in {"geographical_experience", "systems", "expertise"}:
                if value:
                    existing = list(merged.get(key) or [])
                    merged[key] = list(dict.fromkeys([*existing, *value]))
            elif key in {"full_name", "professional_summary"}:
                if value:
                    merged[key] = value
            elif key == "skills":
                if value:
                    existing = list(merged.get("skills") or [])
                    merged["skills"] = list(dict.fromkeys([*existing, *value]))
        return merged

    @staticmethod
    def extract_cv_deterministically(
        extraction_path: str, file_type: str, text: str
    ) -> dict[str, Any]:
        """Build a CV's extraction_result with no LLM call at all.

        All CVs in this system come from one fixed template, and the
        deterministic PDF-table parser (cv_table_extractor.py) already
        outperforms the LLM on it. A CV that doesn't fit the template
        (non-PDF, or the parser finds nothing recognizable) is NOT sent to
        the LLM as a fallback — it is flagged for manual review instead.
        See backend/docs/consultant-knowledge-core.md.
        """
        table_payload: dict[str, Any] = {}
        if file_type == "pdf":
            try:
                from app.services.cv_table_extractor import extract_cv_tables

                table_payload = extract_cv_tables(extraction_path).as_extraction_payload()
            except Exception as exc:
                logger.warning(
                    "Deterministic CV extraction failed for %s: %s", extraction_path, exc
                )
                table_payload = {}

        if not table_payload.get("personal_information") and not table_payload.get("work_history"):
            # A confidence score below CONFIDENCE_REVIEW_THRESHOLD routes
            # through determine_review_status the same way a low-confidence
            # LLM field would — no LLM call happens here, this only reuses
            # that existing review-routing mechanism.
            return {
                "document_type": "cv",
                "extraction_method": "deterministic_failed",
                "confidence": {"all": 0.0},
            }

        extraction_result = CVProcessingService.merge_table_extraction({}, table_payload)
        extracted_training = CVProcessingService.training_from_text(text)
        if extracted_training:
            extraction_result["training_qualifications"] = extracted_training
        extracted_systems = CVProcessingService.systems_from_text(text)
        if extracted_systems:
            extraction_result["systems"] = list(
                dict.fromkeys([*(extraction_result.get("systems") or []), *extracted_systems])
            )
        extraction_result["extraction_method"] = "deterministic"
        return extraction_result

    @staticmethod
    def systems_from_text(text: str) -> list[str]:
        """Recover the complete SYSTEMS EXPERIENCE section from CV text."""
        values: list[str] = []
        keywords = re.compile(
            r"mseis|passive acoustic|navigation|orca|seapronav|fugro|pamguard|lofitech|seal scarer|camera|binocular|laptop|garmin|microsoft|office|qgis|linux|windows",
            re.I,
        )
        active = False
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip(" \t-•")
            upper = line.upper()
            if re.search(r"\bSYSTEMS EXPERIENCE\b", upper) and len(line) < 100:
                active = True
                continue
            if active and re.fullmatch(
                r"(EXPERIENCE|EDUCATION|TRAINING|QUALIFICATIONS|CERTIFICATIONS|REFERENCES|EXPERTISE)",
                upper,
            ):
                break
            if active and line and len(line) > 2 and keywords.search(line):
                values.append(line)
            if len(values) >= 100:
                break
        return list(dict.fromkeys(values))

    async def _create_certifications(
        self,
        session,
        crew_member: CrewMember,
        data: dict[str, Any],
        document_id: str | None,
        summary: dict[str, Any],
    ) -> None:
        """Create certification records from extracted CV data."""
        existing_certs = {c.cert_type for c in crew_member.certifications}

        certs_to_add = set()
        for spec in data.get("specializations", []):
            spec_lower = spec.lower().strip()
            for key, cert_type in CERT_ALIASES.items():
                if key in spec_lower:
                    certs_to_add.add(cert_type)

        for skill in data.get("skills", []):
            skill_lower = skill.lower().strip()
            for key, cert_type in CERT_ALIASES.items():
                if key in skill_lower:
                    certs_to_add.add(cert_type)

        training_values = data.get("training_qualifications") or []
        for cert in [*data.get("certifications", []), *training_values]:
            if isinstance(cert, str):
                cert_lower = cert.lower().strip()
                for key, cert_type in CERT_ALIASES.items():
                    if key in cert_lower:
                        certs_to_add.add(cert_type)

        import uuid

        for cert_type in certs_to_add:
            if cert_type not in existing_certs:
                issue_date, expiry_date = self._certification_dates(cert_type, data)
                certification = Certification(
                    id=str(uuid.uuid4()),
                    crew_member_id=crew_member.id,
                    cert_type=cert_type,
                    status="pending_verification",
                    verification_status="unverified",
                    document_ref=document_id,
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                )
                session.add(certification)
                summary["certifications_created"] += 1
                existing_certs.add(cert_type)

            else:
                # Existing records from earlier extraction runs may have had
                # dates omitted. Fill only missing values from explicit CV
                # date evidence; never overwrite an operator correction.
                existing = next(c for c in crew_member.certifications if c.cert_type == cert_type)
                issue_date, expiry_date = self._certification_dates(cert_type, data)
                if issue_date and not existing.issue_date:
                    existing.issue_date = issue_date
                if expiry_date and not existing.expiry_date:
                    existing.expiry_date = expiry_date

    @classmethod
    def _certification_dates(
        cls, cert_type: str, data: dict[str, Any]
    ) -> tuple[date | None, date | None]:
        """Return explicit completion/expiry dates for a certification."""
        aliases = {
            "JNCC MMO": ("jncc", "mmo", "marine mammal", "protected species observer"),
            "PAMGUARD Advanced": ("pamguard", "pam", "passive acoustic", "mseis"),
            "BOSIET": ("bosiet",),
            "FOET": ("foet",),
            "GWO Wind": ("gwo",),
            "STCW": ("stcw",),
            "OGUK Medical": ("oguk", "medical"),
            "NEBOSH Diploma": ("nebosh",),
            "QPS QINSy": ("qps", "qinsy"),
            "GWO Wind": ("gwo",),
        }.get(cert_type, (cert_type.lower(),))
        expiry_map = data.get("certification_expiry_dates") or {}
        issue_map = data.get("certification_issue_dates") or {}
        expiry = next(
            (
                value
                for key, value in expiry_map.items()
                if any(alias in str(key).lower() for alias in aliases)
            ),
            None,
        )
        issue = next(
            (
                value
                for key, value in issue_map.items()
                if any(alias in str(key).lower() for alias in aliases)
            ),
            None,
        )
        for line in data.get("training_qualifications") or []:
            if not isinstance(line, str) or not any(alias in line.lower() for alias in aliases):
                continue
            dates = re.findall(r"\b(?:\d{1,2}[/-])?\d{1,2}[/-]\d{2,4}\b|\b\d{4}\b", line)
            parsed = [cls._parse_date(value) for value in dates]
            parsed = [value for value in parsed if value]
            if parsed and not issue:
                issue = parsed[0]
            if len(parsed) > 1 and not expiry:
                expiry = parsed[-1]
        return cls._parse_date(issue), cls._parse_date(expiry)

    async def _create_work_history(
        self,
        session,
        crew_member: CrewMember,
        data: dict[str, Any],
        document_id: str | None,
        summary: dict[str, Any],
    ) -> None:
        """Create work history records from extracted CV data."""
        import uuid

        # A document may be reprocessed after an extraction-model upgrade.
        # Its prior work-history rows are already the record for this source;
        # never add a second set merely because wording changed.
        if document_id and any(
            record.document_ref == document_id for record in crew_member.work_history
        ):
            return

        existing_work = {
            (
                record.client_name or "",
                record.project_name or "",
                record.role or "",
                record.start_date,
            )
            for record in crew_member.work_history
        }

        for work in data.get("work_history", []):
            if isinstance(work, dict) and work.get("client"):
                start_date = self._parse_date(work.get("start_date"))
                work_key = (
                    work.get("client", ""),
                    work.get("project", ""),
                    work.get("role", ""),
                    start_date,
                )
                if work_key in existing_work:
                    continue
                work_record = WorkHistory(
                    id=str(uuid.uuid4()),
                    crew_member_id=crew_member.id,
                    client_name=work.get("client", ""),
                    project_name=work.get("project", ""),
                    project_type=work.get("project_type", ""),
                    location=work.get("location", ""),
                    country=work.get("country", ""),
                    role=work.get("role", ""),
                    responsibilities=work.get("responsibilities", ""),
                    start_date=start_date,
                    end_date=self._parse_date(work.get("end_date")),
                    document_ref=document_id,
                )
                session.add(work_record)
                summary["work_history_created"] += 1
                existing_work.add(work_key)

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse date string to date object."""
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y"):
            try:
                return datetime.strptime(str(date_str), fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def _calculate_completeness(crew_member: CrewMember) -> float:
        """Calculate profile completeness score."""
        score = 0.0
        fields = [
            crew_member.email,
            crew_member.phone,
            crew_member.nationality,
            crew_member.passport_number,
            crew_member.medical_status,
            crew_member.country_of_residence,
            crew_member.gender,
            crew_member.flying_point,
            crew_member.date_of_birth,
            crew_member.languages,
        ]
        score += sum(8 for f in fields if f)
        score += min(len(crew_member.certifications) * 5, 30)
        score += min(len(crew_member.work_history) * 5, 20)
        return min(score, 100.0)


cv_processing_service = CVProcessingService()
