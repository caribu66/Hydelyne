from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

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
                    report_data = json.loads(response_text[start:end + 1])
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
