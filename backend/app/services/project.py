from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Project


class ProjectService:
    """Service for project operations."""

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

    async def create_project(self, project: Project) -> Project:
        """Persist a new project.

        ``project`` is an unpersisted model instance built by the caller
        (the GraphQL layer owns mapping the create DTO to a model).
        """
        factory = get_session_factory()
        async with factory() as session:
            session.add(project)
            await session.commit()
            await session.refresh(project)
            return project

    async def update_project(self, project_id: str, status: Optional[str] = None) -> Project:
        """Update a project's status."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Project).where(Project.id == project_id)
            result = await session.execute(stmt)
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            if status is not None:
                project.status = status
            await session.commit()
            await session.refresh(project)
            return project

    async def assign_crew(self, project_id: str, crew_ids: list[str]) -> Project:
        """Assign a set of crew members to a project."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Project).where(Project.id == project_id)
            result = await session.execute(stmt)
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            project.crew_assigned = crew_ids
            await session.commit()
            await session.refresh(project)
            return project


project_service = ProjectService()
