from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.fields import AVAILABILITY_STATUS_VALUES, CERT_STATUS_VALUES
from app.domain.input_limits import validate_pagination
from app.models import Certification, CrewMember, Document, Project
from app.services.ollama import ollama_client
from app.services.project import PROJECT_STATUS_VALUES

logger = logging.getLogger(__name__)

MAX_REPORT_FILTER_VALUE_LENGTH = 100
MAX_REPORT_STATUS_FILTERS = 20
MAX_REPORT_RESPONSE_LENGTH = 20_000
MAX_REPORT_SUMMARY_LENGTH = 2_000
MAX_REPORT_LIST_ITEMS = 20
MAX_REPORT_ITEM_LENGTH = 500


def _contractor_account_condition() -> Any:
    """Keep login accounts out of contractor-facing report data."""
    return and_(
        CrewMember.password_hash.is_(None),
        or_(CrewMember.role.is_(None), CrewMember.role.not_in(("staff", "admin"))),
    )


def _derived_certification_status(
    expiry_date: date | None,
    verification_status: str | None,
    reference_date: date,
) -> str:
    """Derive report status from verified expiry evidence."""
    if verification_status != "verified":
        return "pending_verification"
    if expiry_date is None or expiry_date > reference_date + timedelta(days=30):
        return "valid"
    if expiry_date >= reference_date:
        return "expiring_soon"
    return "expired"


REPORT_NUMERIC_FIELDS = {
    "total_available",
    "compliant_count",
    "non_compliant_count",
    "expiring_30_days",
    "expired",
    "total_evaluations",
    "average_rating",
    "crew_assigned",
    "certifications_complete",
    "certifications_missing",
}
REPORT_LIST_FIELDS = {
    "top_performers",
    "areas_for_improvement",
    "gaps",
    "recommendations",
}

REPORT_TEMPLATES = {
    "availability": """Generate a crew availability report based on the following data.

Data:
{data}

Format the report as JSON:
{{
  "summary": "Brief summary of available crew",
  "total_available": number,
  "crew_by_skill": {{"skill_name": count}},
  "recommendations": ["recommendation_1", "recommendation_2"]
}}""",
    "compliance": """Generate a compliance status report based on the following certification data.

Data:
{data}

Format the report as JSON:
{{
  "summary": "Brief compliance overview",
  "compliant_count": number,
  "non_compliant_count": number,
  "expiring_30_days": number,
  "expired": number,
  "recommendations": ["recommendation_1", "recommendation_2"]
}}""",
    "performance": """Generate a crew performance report based on the following data.

Data:
{data}

Format the report as JSON:
{{
  "summary": "Brief performance overview",
  "total_evaluations": number,
  "average_rating": number,
  "top_performers": ["name_1", "name_2"],
  "areas_for_improvement": ["area_1"],
  "recommendations": ["recommendation_1"]
}}""",
    "project_readiness": """Generate a project readiness report based on the following data.

Data:
{data}

Format the report as JSON:
{{
  "summary": "Brief readiness overview",
  "project": "project name",
  "crew_assigned": number,
  "certifications_complete": number,
  "certifications_missing": number,
  "gaps": ["gap_1"],
  "recommendations": ["recommendation_1"]
}}""",
}


def validate_report_filters(report_type: str, filters: dict[str, Any]) -> None:
    """Reject malformed filter shapes before they reach SQL construction."""
    if report_type == "availability":
        value = filters.get("availability_status")
        if value is not None and not isinstance(value, str):
            raise ValueError("availability_status must be a string")
        if isinstance(value, str) and len(value) > MAX_REPORT_FILTER_VALUE_LENGTH:
            raise ValueError("availability_status is too long")
        if isinstance(value, str) and value not in AVAILABILITY_STATUS_VALUES:
            raise ValueError("Invalid availability_status")
    elif report_type == "compliance":
        value = filters.get("status", filters.get("cert_status"))
        if value is not None and not isinstance(value, (str, list)):
            raise ValueError("status must be a string or list of strings")
        if isinstance(value, list) and not all(isinstance(item, str) for item in value):
            raise ValueError("status must be a string or list of strings")
        if isinstance(value, list) and not value:
            raise ValueError("status must contain at least one value")
        if isinstance(value, list) and len(value) > MAX_REPORT_STATUS_FILTERS:
            raise ValueError(f"status must contain at most {MAX_REPORT_STATUS_FILTERS} values")
        if isinstance(value, str) and len(value) > MAX_REPORT_FILTER_VALUE_LENGTH:
            raise ValueError("status is too long")
        if isinstance(value, list) and any(
            len(item) > MAX_REPORT_FILTER_VALUE_LENGTH for item in value
        ):
            raise ValueError("status contains an overly long value")
        statuses = [value] if isinstance(value, str) else value or []
        if any(status not in CERT_STATUS_VALUES for status in statuses):
            raise ValueError("Invalid certification status")
    elif report_type == "project_readiness":
        value = filters.get("status")
        if value is not None and not isinstance(value, str):
            raise ValueError("status must be a string")
        if isinstance(value, str) and len(value) > MAX_REPORT_FILTER_VALUE_LENGTH:
            raise ValueError("status is too long")
        if isinstance(value, str) and value not in PROJECT_STATUS_VALUES:
            raise ValueError("Invalid project status")


class ReportService:
    """Service for generating formatted reports using LLM."""

    @staticmethod
    def _load_report_json(response_text: str) -> Any:
        """Parse strict JSON from the report model."""

        def reject_non_standard_number(value: str) -> None:
            raise ValueError(f"Non-standard JSON number: {value}")

        return json.loads(response_text, parse_constant=reject_non_standard_number)

    @staticmethod
    def _sanitize_report_data(report_data: Any) -> dict[str, Any]:
        """Keep only bounded, typed fields from an untrusted model response."""
        if not isinstance(report_data, dict):
            return {"summary": "The report model returned an invalid response."}

        sanitized: dict[str, Any] = {}
        summary = report_data.get("summary")
        if isinstance(summary, str):
            sanitized["summary"] = summary[:MAX_REPORT_SUMMARY_LENGTH]
        else:
            sanitized["summary"] = ""

        for field in REPORT_NUMERIC_FIELDS:
            value = report_data.get(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if math.isfinite(float(value)):
                    sanitized[field] = value

        for field in REPORT_LIST_FIELDS:
            value = report_data.get(field)
            if isinstance(value, list):
                sanitized[field] = [
                    item[:MAX_REPORT_ITEM_LENGTH]
                    for item in value[:MAX_REPORT_LIST_ITEMS]
                    if isinstance(item, str)
                ]

        crew_by_skill = report_data.get("crew_by_skill")
        if isinstance(crew_by_skill, dict):
            sanitized["crew_by_skill"] = {
                str(skill)[:MAX_REPORT_ITEM_LENGTH]: value
                for skill, value in list(crew_by_skill.items())[:MAX_REPORT_LIST_ITEMS]
                if isinstance(skill, str)
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
            }
        return sanitized

    async def build_report_data(
        self,
        report_type: str,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[dict[str, Any]] = None,
        actor_id: Optional[str] = None,
        actor_role: str = "user",
    ) -> dict[str, Any]:
        """Deterministically gather the raw data a report is built from.

        Runs before any LLM enrichment so a report always has a factual
        basis, and so build_fallback_summary has something to summarize if
        the LLM is unavailable. Counts are totals (COUNT(*)), not page sizes.
        """
        from sqlalchemy import func

        if report_type not in REPORT_TEMPLATES:
            raise ValueError(f"Unknown report type: {report_type}")
        if filters is not None and not isinstance(filters, dict):
            raise ValueError("Report filters must be an object")
        applied = filters or {}
        validate_report_filters(report_type, applied)
        limit, offset = validate_pagination(limit, offset)

        def crew_scope(stmt: Any) -> Any:
            """Restrict crew-backed reports to visible publication scope."""
            stmt = stmt.where(_contractor_account_condition())
            if actor_role == "admin":
                return stmt
            if actor_role == "staff" and actor_id:
                return stmt.where(
                    or_(
                        CrewMember.publication_status == "approved",
                        and_(
                            CrewMember.publication_status == "draft",
                            CrewMember.submitted_by == actor_id,
                        ),
                    )
                )
            return stmt.where(CrewMember.publication_status == "approved")

        if report_type == "availability":
            status_filter = applied.get("availability_status") or "available"
            crew_base = crew_scope(
                select(CrewMember).where(CrewMember.availability_status == status_filter)
            )
            total = (
                await session.execute(select(func.count()).select_from(crew_base.subquery()))
            ).scalar_one()
            crew_result = await session.execute(
                crew_base.order_by(CrewMember.created_at.desc(), CrewMember.id.desc())
                .limit(limit)
                .offset(offset)
            )
            crew_list = crew_result.scalars().all()
            return {
                "available_count": int(total),
                "crew": [{"id": c.id, "name": c.full_name} for c in crew_list],
            }
        if report_type == "compliance":
            statuses = (
                applied.get("status") or applied.get("cert_status") or ["expired", "expiring_soon"]
            )
            if isinstance(statuses, str):
                statuses = [statuses]
            today = date.today()
            status_conditions = []
            for status in statuses:
                if status == "pending_verification":
                    status_conditions.append(
                        or_(
                            Certification.verification_status.is_(None),
                            Certification.verification_status == "unverified",
                        )
                    )
                elif status == "valid":
                    status_conditions.append(
                        and_(
                            Certification.verification_status == "verified",
                            or_(
                                Certification.expiry_date.is_(None),
                                Certification.expiry_date > today + timedelta(days=30),
                            ),
                        )
                    )
                elif status == "expiring_soon":
                    status_conditions.append(
                        and_(
                            Certification.verification_status == "verified",
                            Certification.expiry_date >= today,
                            Certification.expiry_date <= today + timedelta(days=30),
                        )
                    )
                elif status == "expired":
                    status_conditions.append(
                        and_(
                            Certification.verification_status == "verified",
                            Certification.expiry_date < today,
                        )
                    )
            cert_base = crew_scope(
                select(Certification)
                .join(CrewMember, Certification.crew_member_id == CrewMember.id)
                .where(
                    or_(
                        Certification.status.is_(None),
                        Certification.status != "rejected",
                    ),
                    or_(
                        Certification.verification_status.is_(None),
                        Certification.verification_status != "rejected",
                    ),
                    or_(*status_conditions),
                )
            )
            total = (
                await session.execute(select(func.count()).select_from(cert_base.subquery()))
            ).scalar_one()
            cert_result = await session.execute(
                cert_base.order_by(Certification.expiry_date.asc(), Certification.id.asc())
                .limit(limit)
                .offset(offset)
            )
            certs = cert_result.scalars().all()
            return {
                "non_compliant_count": int(total),
                "certifications": [
                    {
                        "id": c.id,
                        "type": c.cert_type,
                        "status": _derived_certification_status(
                            c.expiry_date, c.verification_status, today
                        ),
                        "expiry": str(c.expiry_date) if c.expiry_date else None,
                    }
                    for c in certs
                ],
            }
        if report_type == "project_readiness":
            proj_base = select(Project)
            if applied.get("status"):
                proj_base = proj_base.where(Project.status == str(applied["status"]))
            total = (
                await session.execute(select(func.count()).select_from(proj_base.subquery()))
            ).scalar_one()
            project_result = await session.execute(
                proj_base.order_by(Project.created_at.desc(), Project.id.desc())
                .limit(limit)
                .offset(offset)
            )
            projects = project_result.scalars().all()
            visibility = _contractor_account_condition()
            if actor_role != "admin":
                visibility = and_(visibility, CrewMember.publication_status == "approved")
                if actor_role == "staff" and actor_id:
                    visibility = or_(
                        visibility,
                        and_(
                            _contractor_account_condition(),
                            CrewMember.publication_status == "draft",
                            CrewMember.submitted_by == actor_id,
                        ),
                    )
            visible_rows = await session.execute(select(CrewMember.id).where(visibility))
            visible_crew_ids = set(visible_rows.scalars().all())
            return {
                "project_count": int(total),
                "projects": [
                    {
                        "id": p.id,
                        "name": p.project_name,
                        "client": p.client_name,
                        "status": p.status,
                        "crew_assigned": [
                            crew_id
                            for crew_id in (p.crew_assigned or [])
                            if visible_crew_ids is None or crew_id in visible_crew_ids
                        ],
                    }
                    for p in projects
                ],
            }
        # performance: performance data lives in document extracted_data; summarize what we have
        doc_base = crew_scope(
            select(Document)
            .join(CrewMember, Document.crew_member_id == CrewMember.id)
            .where(
                Document.classification == "performance",
                Document.extraction_status.in_({"approved", "extracted"}),
                or_(
                    Document.uploaded_by.is_(None),
                    Document.uploaded_by != "contractor-upload-link",
                    Document.extraction_status == "approved",
                ),
            )
        )
        total = (
            await session.execute(select(func.count()).select_from(doc_base.subquery()))
        ).scalar_one()
        doc_result = await session.execute(
            doc_base.order_by(Document.uploaded_at.desc(), Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
        perf_docs = doc_result.scalars().all()
        return {
            "performance_document_count": int(total),
            "documents": [
                {
                    "id": d.id,
                    "file_name": d.file_name,
                    "extraction_status": d.extraction_status,
                }
                for d in perf_docs
            ],
        }

    def build_fallback_summary(self, report_type: str, data: dict[str, Any]) -> str:
        """Deterministic summary used when the LLM enrichment call fails."""
        if report_type == "availability":
            return f"{data.get('available_count', 0)} crew members currently available."
        if report_type == "compliance":
            return f"{data.get('non_compliant_count', 0)} certifications require attention."
        return f"{report_type.title()} report generated successfully."

    async def generate_report(
        self,
        report_type: str,
        data: dict,
        filters: Optional[dict] = None,
    ) -> dict:
        """Generate a formatted report using LLM.

        Args:
            report_type: Type of report (availability, compliance, performance, project_readiness).
            data: Raw data to include in the report.
            filters: Optional filters applied to the data.

        Returns:
            Dict containing the formatted report.
        """
        template = REPORT_TEMPLATES.get(report_type)
        if not template:
            raise ValueError(f"Unknown report type: {report_type}")

        prompt = template.format(data=json.dumps(data, indent=2, default=str))

        try:
            result = await ollama_client.extract(
                prompt=prompt,
                model=ollama_client.report_model,
            )
            response_text = result.get("response", "")

            try:
                if not isinstance(response_text, str):
                    raise ValueError("Report model returned a non-string response")
                if len(response_text) > MAX_REPORT_RESPONSE_LENGTH:
                    raise ValueError("Report model response is too large")
                report_data = self._load_report_json(response_text)
            except (json.JSONDecodeError, ValueError):
                if (
                    isinstance(response_text, str)
                    and len(response_text) <= MAX_REPORT_RESPONSE_LENGTH
                ):
                    start = response_text.find("{")
                    end = response_text.rfind("}")
                else:
                    start = end = -1
                if start != -1 and end != -1:
                    report_data = self._load_report_json(response_text[start : end + 1])
                else:
                    report_data = {"summary": "The report model returned an invalid response."}

            report_data = self._sanitize_report_data(report_data)
            summary = report_data.get("summary", "")

            return {
                "id": str(uuid.uuid4()),
                "report_type": report_type,
                "title": f"{report_type.replace('_', ' ').title()} Report",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "filters": json.dumps(filters) if filters else None,
                "summary": summary,
                "data": json.dumps(report_data),
                "recommendations": json.dumps(report_data.get("recommendations", [])),
            }
        except Exception as e:
            logger.error("Report generation failed: %s", type(e).__name__)
            return {
                "id": str(uuid.uuid4()),
                "report_type": report_type,
                "title": f"{report_type.replace('_', ' ').title()} Report",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": "Report generation failed. Please try again.",
                "data": json.dumps(data),
                "recommendations": "[]",
            }


report_service = ReportService()
