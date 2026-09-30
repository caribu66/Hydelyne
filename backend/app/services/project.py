from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, or_, select

from app.database import get_session_factory
from app.domain.crew_accounts import is_contractor_profile
from app.domain.input_limits import validate_pagination
from app.models import CrewMember, Project

PROJECT_STATUS_VALUES = frozenset({"planning", "active", "completed", "cancelled"})
PROJECT_TEXT_LIMITS = {
    "client_name": 255,
    "project_name": 255,
    "project_type": 50,
    "location": 255,
    "country": 100,
    "water_depth": 50,
    "document_ref": 255,
}
PROJECT_CREW_ID_MAX_LENGTH = 36


def _validate_project_values(project: Project) -> None:
    """Validate raw project model values before persistence."""
    for field, maximum in PROJECT_TEXT_LIMITS.items():
        value = getattr(project, field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        if field in {"client_name", "project_name", "project_type"} and not value.strip():
            raise ValueError(f"{field} must not be empty")
        if len(value) > maximum:
            raise ValueError(f"{field} must be {maximum} characters or fewer")
    if project.status is not None and (
        not isinstance(project.status, str) or project.status not in PROJECT_STATUS_VALUES
    ):
        raise ValueError(f"Invalid project status: {project.status}")
    if project.start_date is not None and (
        not isinstance(project.start_date, date) or isinstance(project.start_date, datetime)
    ):
        raise ValueError("start_date must be a date")
    if project.end_date is not None and (
        not isinstance(project.end_date, date) or isinstance(project.end_date, datetime)
    ):
        raise ValueError("end_date must be a date")
    if (
        project.start_date is not None
        and project.end_date is not None
        and project.start_date > project.end_date
    ):
        raise ValueError("start_date must be on or before end_date")


def _validate_crew_ids(crew_ids: list[str]) -> None:
    """Validate assignment IDs before constructing a database IN clause."""
    if not isinstance(crew_ids, list):
        raise ValueError("crew_ids must be a list")
    for crew_id in crew_ids:
        if not isinstance(crew_id, str) or not crew_id.strip():
            raise ValueError("crew_ids must contain non-empty strings")
        if len(crew_id) > PROJECT_CREW_ID_MAX_LENGTH:
            raise ValueError(
                f"crew_ids values must be {PROJECT_CREW_ID_MAX_LENGTH} characters or fewer"
            )


class ProjectService:
    """Service for project operations."""

    async def visible_crew_assignments(
        self,
        projects: list[Project],
        *,
        actor_id: str,
        actor_role: str,
    ) -> dict[str, list[str]]:
        """Return assignment IDs visible to the actor for each project."""
        assignments_by_project: dict[str, list[str]] = {}
        assigned_ids: set[str] = set()
        for project in projects:
            assignments = project.crew_assigned
            visible_input = (
                [item for item in assignments if isinstance(item, str)]
                if isinstance(assignments, list)
                else []
            )
            assignments_by_project[project.id] = visible_input
            assigned_ids.update(visible_input)

        if not assigned_ids:
            return assignments_by_project

        async with get_session_factory()() as session:
            conditions = [
                CrewMember.id.in_(assigned_ids),
                CrewMember.password_hash.is_(None),
                or_(CrewMember.role.is_(None), CrewMember.role.not_in(("staff", "admin"))),
            ]
            if actor_role != "admin":
                conditions.append(
                    or_(
                        CrewMember.publication_status == "approved",
                        and_(
                            CrewMember.publication_status == "draft",
                            CrewMember.submitted_by == actor_id,
                        ),
                    )
                )
            visible_stmt = select(CrewMember.id).where(*conditions)
            visible_ids = set((await session.execute(visible_stmt)).scalars())

        return {
            project_id: [crew_id for crew_id in crew_ids if crew_id in visible_ids]
            for project_id, crew_ids in assignments_by_project.items()
        }

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Project).where(Project.id == project_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_projects(
        self,
        status: Optional[str] = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Project]:
        """List projects, optionally filtered by status."""
        limit, offset = validate_pagination(limit, offset)
        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(Project)
                .order_by(Project.created_at.desc(), Project.id.desc())
                .limit(limit)
                .offset(offset)
            )
            if status:
                stmt = stmt.where(Project.status == status)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_project(self, project: Project) -> Project:
        """Persist a new project.

        ``project`` is an unpersisted model instance built by the caller
        (the GraphQL layer owns mapping the create DTO to a model).
        """
        _validate_project_values(project)
        factory = get_session_factory()
        async with factory() as session:
            session.add(project)
            await session.commit()
            await session.refresh(project)
            return project

    async def update_project(self, project_id: str, status: Optional[str] = None) -> Project:
        """Update a project's status."""
        if status is not None and (
            not isinstance(status, str) or status not in PROJECT_STATUS_VALUES
        ):
            raise ValueError(f"Invalid project status: {status}")
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(Project).where(Project.id == project_id).with_for_update()
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
        _validate_crew_ids(crew_ids)
        unique_crew_ids = list(dict.fromkeys(crew_ids))
        if len(unique_crew_ids) != len(crew_ids):
            raise ValueError("crew_ids must not contain duplicates")
        factory = get_session_factory()
        async with factory() as session:
            if unique_crew_ids:
                existing_crew = list(
                    (
                        await session.execute(
                            select(CrewMember)
                            .where(CrewMember.id.in_(unique_crew_ids))
                            .with_for_update()
                        )
                    ).scalars()
                )
                crew_by_id = {crew.id: crew for crew in existing_crew}
                if any(
                    crew_id not in crew_by_id
                    or not is_contractor_profile(crew_by_id[crew_id])
                    for crew_id in unique_crew_ids
                ):
                    raise ValueError("One or more crew members were not found")
            stmt = select(Project).where(Project.id == project_id).with_for_update()
            result = await session.execute(stmt)
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            project.crew_assigned = crew_ids
            await session.commit()
            await session.refresh(project)
            return project


project_service = ProjectService()
