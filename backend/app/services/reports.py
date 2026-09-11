from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Certification, CrewMember, Document, Project
from app.services.ollama import ollama_client

logger = logging.getLogger(__name__)

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


class ReportService:
    """Service for generating formatted reports using LLM."""

    async def build_report_data(
        self,
        report_type: str,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Deterministically gather the raw data a report is built from.

        Runs before any LLM enrichment so a report always has a factual
        basis, and so build_fallback_summary has something to summarize if
        the LLM is unavailable. Counts are totals (COUNT(*)), not page sizes.
        """
        from sqlalchemy import func

        applied = filters or {}
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        if report_type == "availability":
            status_filter = str(applied.get("availability_status", "available"))
            crew_base = select(CrewMember).where(CrewMember.availability_status == status_filter)
            total = (
                await session.execute(select(func.count()).select_from(crew_base.subquery()))
            ).scalar_one()
            crew_result = await session.execute(crew_base.limit(limit).offset(offset))
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
            cert_base = select(Certification).where(Certification.status.in_(list(statuses)))
            total = (
                await session.execute(select(func.count()).select_from(cert_base.subquery()))
            ).scalar_one()
            cert_result = await session.execute(cert_base.limit(limit).offset(offset))
            certs = cert_result.scalars().all()
            return {
                "non_compliant_count": int(total),
                "certifications": [
                    {
                        "id": c.id,
                        "type": c.cert_type,
                        "status": c.status,
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
            project_result = await session.execute(proj_base.limit(limit).offset(offset))
            projects = project_result.scalars().all()
            return {
                "project_count": int(total),
                "projects": [
                    {
                        "id": p.id,
                        "name": p.project_name,
                        "client": p.client_name,
                        "status": p.status,
                        "crew_assigned": (p.crew_assigned or []),
                    }
                    for p in projects
                ],
            }
        # performance: performance data lives in document extracted_data; summarize what we have
        doc_base = select(Document).where(Document.classification == "performance")
        total = (
            await session.execute(select(func.count()).select_from(doc_base.subquery()))
        ).scalar_one()
        doc_result = await session.execute(doc_base.limit(limit).offset(offset))
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
                report_data = json.loads(response_text)
            except json.JSONDecodeError:
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    report_data = json.loads(response_text[start : end + 1])
                else:
                    report_data = {
                        "summary": response_text[:500],
                        "raw_response": response_text,
                    }

            return {
                "id": str(uuid.uuid4()),
                "report_type": report_type,
                "title": f"{report_type.replace('_', ' ').title()} Report",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "filters": json.dumps(filters) if filters else None,
                "summary": report_data.get("summary", ""),
                "data": json.dumps(report_data),
                "recommendations": json.dumps(report_data.get("recommendations", [])),
            }
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
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
