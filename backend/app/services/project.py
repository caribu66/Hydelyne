from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Project


class ProjectService:
    """Service for project read operations."""

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Project).where(Project.id == project_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_projects(self, status: Optional[str] = None) -> list[Project]:
        """List projects, optionally filtered by status."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Project)
            if status:
                stmt = stmt.where(Project.status == status)
            result = await session.execute(stmt)
            return list(result.scalars().all())


project_service = ProjectService()
