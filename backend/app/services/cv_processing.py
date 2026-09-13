"""Service to process extracted CV data and populate crew member profile."""

from __future__ import annotations

import logging
import math
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session_factory
from app.domain.certifications import CERT_ALIASES
from app.domain.crew_accounts import is_contractor_profile
from app.models import Certification, CrewMember, Document, WorkHistory

logger = logging.getLogger(__name__)

CV_SHORT_TEXT_MAX_LENGTH = 255
CV_RESPONSIBILITIES_MAX_LENGTH = 20_000
CV_LIST_MAX_ITEMS = 100
CV_REVIEW_TEXT_MAX_LENGTH = 20_000
CV_REVIEW_OBJECT_MAX_FIELDS = 100


def _bounded_cv_text(value: object, max_length: int = CV_SHORT_TEXT_MAX_LENGTH) -> str | None:
    """Return bounded scalar CV text suitable for fixed-width persistence."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        return None
    return normalized


def _bounded_cv_values(value: object) -> list[str]:
    """Return bounded scalar values from a model-produced list."""
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        bounded = _bounded_cv_text(item)
        if bounded and bounded not in values:
            values.append(bounded)
        if len(values) >= CV_LIST_MAX_ITEMS:
            break
    return values


def _bound_cv_review_payload(value: object, depth: int = 0) -> object:
    """Bound deterministic parser output before it enters the review queue."""
    if depth > 3:
        return None
    if isinstance(value, str):
        return value[:CV_REVIEW_TEXT_MAX_LENGTH]
    if isinstance(value, list):
        return [_bound_cv_review_payload(item, depth + 1) for item in value[:CV_LIST_MAX_ITEMS]]
    if isinstance(value, dict):
        bounded: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= CV_REVIEW_OBJECT_MAX_FIELDS:
                break
            if isinstance(key, str):
                bounded[key] = _bound_cv_review_payload(item, depth + 1)
        return bounded
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return None


class CVProcessingService:
    """Process extracted CV data and populate crew member records."""

    async def process_cv_extraction(
        self,
        crew_member_id: str,
        extracted_data: dict[str, Any],
        document_id: str | None = None,
        *,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        """Process extracted CV data and update crew member profile.

        Returns summary of what was created/updated.
        """
        if not isinstance(extracted_data, dict):
            raise ValueError("Extracted CV data must be a JSON object")
        factory = get_session_factory()

        async with factory() as session:
            crew = await session.execute(
                select(CrewMember)
                .options(
                    selectinload(CrewMember.certifications),
                    selectinload(CrewMember.work_history),
                )
                .where(CrewMember.id == crew_member_id)
                .with_for_update()
            )
            crew_member = crew.scalar_one_or_none()

            if not crew_member:
                logger.error(f"Crew member {crew_member_id} not found")
                return {"error": "Crew member not found"}

            result_summary = await self.apply_reviewed_extraction(
                session=session,
                crew_member=crew_member,
                extracted_data=extracted_data,
                document_id=document_id,
                replace_existing=replace_existing,
            )
            await session.commit()

        from app.services.cache import cache_service

        # A newly-processed or re-processed CV changes the exact data an AI
        # summary would describe — a stale cached one would show outdated facts.
        await cache_service.delete(cache_service._make_key("summary", crew_member_id))

        return result_summary

    async def apply_reviewed_extraction(
        self,
        *,
        session: AsyncSession,
        crew_member: CrewMember,
        extracted_data: dict[str, Any],
        document_id: str | None,
        replace_existing: bool,
    ) -> dict[str, Any]:
        """Apply reviewed fields without committing the caller's transaction."""
        if not isinstance(extracted_data, dict):
            raise ValueError("Extracted CV data must be a JSON object")
        if not is_contractor_profile(crew_member):
            raise ValueError("Crew member not found")
        result_summary: dict[str, Any] = {
            "certifications_created": 0,
            "work_history_created": 0,
            "fields_updated": [],
        }
        if replace_existing:
            await self._clear_profile(session, crew_member)
        self._update_crew_fields(
            crew_member,
            extracted_data,
            result_summary,
            replace_existing=replace_existing,
        )
        await self._create_certifications(
            session, crew_member, extracted_data, document_id, result_summary
        )
        await self._create_work_history(
            session, crew_member, extracted_data, document_id, result_summary
        )
        crew_member.profile_completeness_score = self._calculate_completeness(crew_member)
        await session.flush()
        return result_summary

    @staticmethod
    async def _clear_profile(session: AsyncSession, crew_member: CrewMember) -> None:
        """Clear canonical CV fields inside the import transaction.

        This is used only after explicit administrator approval. Keeping the
        clear and replacement in one transaction means an import error rolls
        the complete previous profile back instead of exposing partial data.

        Preserve manually entered and independently verified evidence. Only
        rows whose source document is itself a CV belong to this replacement.
        """
        for field in (
            "nationality",
            "country_of_residence",
            "date_of_birth",
            "gender",
            "languages",
            "flying_point",
            "address",
            "education",
            "professional_summary",
            "geographical_experience",
            "systems_experience",
            "training_qualifications",
            "tags",
            "experience_months",
        ):
            setattr(crew_member, field, None)
        referenced_document_ids = {
            row.document_ref
            for row in [*crew_member.certifications, *crew_member.work_history]
            if row.document_ref
        }
        if not referenced_document_ids:
            return

        cv_document_ids = set(
            (
                await session.execute(
                    select(Document.id).where(
                        Document.id.in_(referenced_document_ids),
                        Document.classification == "cv",
                    )
                )
            )
            .scalars()
            .all()
        )
        if not cv_document_ids:
            return

        detached_certification_ids: list[str] = []
        detached_expiry_dates = []
        for certification in list(crew_member.certifications):
            if certification.document_ref in cv_document_ids:
                detached_certification_ids.append(certification.id)
                detached_expiry_dates.append(certification.expiry_date)
                crew_member.certifications.remove(certification)
        for work_history in list(crew_member.work_history):
            if work_history.document_ref in cv_document_ids:
                crew_member.work_history.remove(work_history)

        if detached_certification_ids:
            from app.services.certification_projection import (
                reconcile_medical_profile_after_detachment,
            )

            await reconcile_medical_profile_after_detachment(
                session,
                crew_id=crew_member.id,
                detached_certification_ids=detached_certification_ids,
                detached_expiry_dates=detached_expiry_dates,
            )

    def _update_crew_fields(
        self,
        crew_member: CrewMember,
        data: dict[str, Any],
        summary: dict[str, Any],
        *,
        replace_existing: bool = False,
    ) -> None:
        """Update crew member basic fields from extracted data."""
        # A CV-only import creates a deliberately recognisable placeholder.
        # Replacement approval may explicitly change an existing name, but an
        # omitted name must preserve the operator's current value.
        full_name = _bounded_cv_text(data.get("full_name"))
        if full_name and (
            replace_existing or crew_member.full_name.strip().lower() == "pending cv import"
        ):
            crew_member.full_name = full_name
            summary["fields_updated"].append("full_name")

        email = _bounded_cv_text(data.get("email"))
        if email and not crew_member.email:
            crew_member.email = email
            summary["fields_updated"].append("email")

        phone = _bounded_cv_text(data.get("phone"), 50)
        if phone and not crew_member.phone:
            crew_member.phone = phone
            summary["fields_updated"].append("phone")

        nationality = _bounded_cv_text(data.get("nationality"), 100)
        if nationality and not crew_member.nationality:
            crew_member.nationality = nationality
            summary["fields_updated"].append("nationality")

        country_of_residence = _bounded_cv_text(data.get("country_of_residence"), 100)
        if country_of_residence and not crew_member.country_of_residence:
            crew_member.country_of_residence = country_of_residence
            summary["fields_updated"].append("country_of_residence")

        gender = _bounded_cv_text(data.get("gender"), 50)
        if gender and not crew_member.gender:
            crew_member.gender = gender
            summary["fields_updated"].append("gender")

        flying_point = _bounded_cv_text(data.get("flying_point"))
        if flying_point and not crew_member.flying_point:
            crew_member.flying_point = flying_point
            summary["fields_updated"].append("flying_point")

        languages = data.get("languages")
        if languages and not crew_member.languages:
            if isinstance(languages, list):
                normalized_languages = _bounded_cv_values(languages)
            elif isinstance(languages, str):
                normalized_languages = _bounded_cv_values(re.split(r",|;", languages))
            else:
                normalized_languages = []
            if normalized_languages:
                crew_member.languages = normalized_languages
                summary["fields_updated"].append("languages")

        if data.get("date_of_birth") and not crew_member.date_of_birth:
            parsed_dob = self._parse_date(data.get("date_of_birth"))
            if parsed_dob:
                crew_member.date_of_birth = parsed_dob
                summary["fields_updated"].append("date_of_birth")

        address = _bounded_cv_text(data.get("address"), 20_000)
        if address and not crew_member.address:
            crew_member.address = address
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

        professional_summary = _bounded_cv_text(data.get("professional_summary"), 20_000)
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
            for value in _bounded_cv_values(data.get(key)):
                if value not in values:
                    values.append(value)
                if len(values) >= CV_LIST_MAX_ITEMS:
                    return values
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
                value = _bounded_cv_text(work.get(field))
                if value and value not in locations:
                    locations.append(value)
        return list(dict.fromkeys(locations))

    @staticmethod
    def _systems_experience(data: dict[str, Any]) -> list[str]:
        """Collect explicit software/equipment/system names from a CV."""
        values = _bounded_cv_values(data.get("systems"))
        pattern = re.compile(
            r"\b(PAMGuard|ADD(?:\s+Lofitech)?|QGIS|Microsoft Office(?: Suite)?)\b", re.I
        )
        for value in _bounded_cv_values(data.get("skills")):
            match = pattern.search(value)
            if match:
                extracted = _bounded_cv_text(match.group(1))
                if extracted:
                    values.append(extracted)
        return list(dict.fromkeys(values))

    @staticmethod
    def _training_qualifications(data: dict[str, Any]) -> list[str]:
        values: list[str] = []
        qualifications = data.get("qualifications") or []
        if isinstance(qualifications, list):
            for item in qualifications:
                if isinstance(item, str) and item.strip():
                    bounded = _bounded_cv_text(item)
                    if bounded:
                        values.append(bounded)
                elif isinstance(item, dict):
                    parts = [
                        str(item.get(key)).strip()
                        for key in ("degree", "field", "institution", "year")
                        if item.get(key)
                    ]
                    if parts:
                        bounded = _bounded_cv_text(" — ".join(parts))
                        if bounded:
                            values.append(bounded)
        for value in _bounded_cv_values(
            data.get("training_qualifications") or data.get("certifications")
        ):
            values.append(value)
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
                bounded = _bounded_cv_text(line)
                if bounded:
                    values.append(bounded)
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
        # Only fall back to the regex text scan when the table extractor
        # found nothing — it did here and its output was already correct.
        # training_from_text scans raw flattened page text line-by-line, so
        # a training table whose cells wrap across multiple visual lines
        # (common — see cv_table_extractor.py's module docstring) gets torn
        # into misordered fragments; unconditionally overwriting a working
        # table-derived result with that was a real data-corruption bug
        # found via a real CV (backend/tests/fixtures_helena_cv.pdf).
        if not extraction_result.get("training_qualifications"):
            extracted_training = CVProcessingService.training_from_text(text)
            if extracted_training:
                extraction_result["training_qualifications"] = extracted_training
        extracted_systems = CVProcessingService.systems_from_text(text)
        if extracted_systems:
            extraction_result["systems"] = list(
                dict.fromkeys([*(extraction_result.get("systems") or []), *extracted_systems])
            )
        extraction_result["extraction_method"] = "deterministic"
        bounded_result = _bound_cv_review_payload(extraction_result)
        if not isinstance(bounded_result, dict):
            raise RuntimeError("Deterministic CV payload must remain a JSON object")
        return {str(key): value for key, value in bounded_result.items()}

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
                bounded = _bounded_cv_text(line)
                if bounded:
                    values.append(bounded)
            if len(values) >= 100:
                break
        return list(dict.fromkeys(values))

    async def _create_certifications(
        self,
        session: AsyncSession,
        crew_member: CrewMember,
        data: dict[str, Any],
        document_id: str | None,
        summary: dict[str, Any],
    ) -> None:
        """Create certification records from extracted CV data."""
        existing_certs = {c.cert_type for c in crew_member.certifications}

        certs_to_add = set()
        for spec in data.get("specializations") or []:
            if not isinstance(spec, str):
                continue
            spec_lower = spec.lower().strip()
            for key, cert_type in CERT_ALIASES.items():
                if key in spec_lower:
                    certs_to_add.add(cert_type)

        for skill in data.get("skills") or []:
            if not isinstance(skill, str):
                continue
            skill_lower = skill.lower().strip()
            for key, cert_type in CERT_ALIASES.items():
                if key in skill_lower:
                    certs_to_add.add(cert_type)

        certification_values = data.get("certifications")
        training_values = data.get("training_qualifications")
        source_values = [
            value
            for values in (certification_values, training_values)
            if isinstance(values, list)
            for value in values
        ]
        for cert in source_values:
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
        }.get(cert_type, (cert_type.lower(),))
        expiry_map = data.get("certification_expiry_dates")
        if not isinstance(expiry_map, dict):
            expiry_map = {}
        issue_map = data.get("certification_issue_dates")
        if not isinstance(issue_map, dict):
            issue_map = {}
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
        training_values = data.get("training_qualifications")
        if not isinstance(training_values, list):
            training_values = []
        for line in training_values:
            if not isinstance(line, str) or not any(alias in line.lower() for alias in aliases):
                continue
            dates = re.findall(r"\b(?:\d{1,2}[/-])?\d{1,2}[/-]\d{2,4}\b|\b\d{4}\b", line)
            parsed = [cls._parse_date(value) for value in dates]
            parsed = [value for value in parsed if value]
            if parsed and not issue:
                issue = parsed[0]
            if len(parsed) > 1 and not expiry:
                expiry = parsed[-1]
        issue_date = cls._parse_date(issue)
        expiry_date = cls._parse_date(expiry)
        if issue_date and expiry_date and expiry_date < issue_date:
            logger.warning("Ignoring reversed CV certification expiry date")
            expiry_date = None
        return issue_date, expiry_date

    async def _create_work_history(
        self,
        session: AsyncSession,
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

        work_history = data.get("work_history")
        if not isinstance(work_history, list):
            work_history = []
        for work in work_history:
            if isinstance(work, dict):
                client_name = _bounded_cv_text(work.get("client"))
                if not client_name:
                    continue
                project_name = _bounded_cv_text(work.get("project"))
                project_type = _bounded_cv_text(work.get("project_type"))
                location = _bounded_cv_text(work.get("location"))
                country = _bounded_cv_text(work.get("country"))
                role = _bounded_cv_text(work.get("role"))
                responsibilities = _bounded_cv_text(
                    work.get("responsibilities"), CV_RESPONSIBILITIES_MAX_LENGTH
                )
                start_date = self._parse_date(work.get("start_date"))
                end_date = self._parse_date(work.get("end_date"))
                if start_date and end_date and end_date < start_date:
                    logger.warning("Ignoring reversed CV work-history end date")
                    end_date = None
                work_key = (
                    client_name,
                    project_name or "",
                    role or "",
                    start_date,
                )
                if work_key in existing_work:
                    continue
                work_record = WorkHistory(
                    id=str(uuid.uuid4()),
                    crew_member_id=crew_member.id,
                    client_name=client_name,
                    project_name=project_name,
                    project_type=project_type,
                    location=location,
                    country=country,
                    role=role,
                    responsibilities=responsibilities,
                    start_date=start_date,
                    end_date=end_date,
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
