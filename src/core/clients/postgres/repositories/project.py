from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_expression

from fastapi import Depends
from src.core.clients.postgres.client import get_db
from src.core.clients.postgres.models.case_file import CaseFile
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.repositories.base import BaseRepository
from src.core.clients.postgres.repositories.version import content_digest
from src.core.pagination.page import PageRequest, paginate

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]

LATEST_PLANT_NUMBER = (
    select(func.max(PlantVersion.number))
    .where(PlantVersion.project_id == Project.id)
    .correlate(Project)
    .scalar_subquery()
)


@dataclass(frozen=True, slots=True)
class ImportedVersion:
    number: int
    note: str
    created: datetime
    content: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ImportedCaseFile:
    name: str
    size: int
    object_key: str


@dataclass(frozen=True, slots=True)
class ImportedCase:
    number: int
    note: str
    created: datetime
    content: dict[str, Any]
    files: list[ImportedCaseFile]
    missing: int


class ProjectRepository(BaseRepository):
    def select_projects(self) -> Select:
        return (
            select(Project)
            .options(with_expression(Project.plant_version, LATEST_PLANT_NUMBER))
            .execution_options(populate_existing=True)
        )

    async def get_by_id(self, project_id: UUID) -> Project | None:
        statement = self.select_projects().where(Project.id == project_id)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        page: PageRequest,
        owner_id: UUID | None = None,
        search: str | None = None,
    ) -> list[Project]:
        statement = self.select_projects()
        if owner_id is not None:
            statement = statement.where(Project.owner_id == owner_id)
        if search:
            statement = statement.where(Project.name.icontains(search, autoescape=True))
        statement = paginate(statement, Project.created, Project.id, page)
        return list(await self.session.scalars(statement))

    async def create(self, name: str, owner_id: UUID) -> Project:
        project = Project(name=name, owner_id=owner_id)
        self.session.add(project)
        await self.session.commit()
        return await self.get_by_id(project.id)

    async def rename(self, project: Project, name: str) -> Project:
        project.name = name
        await self.session.commit()
        return project

    async def create_with_versions(
        self,
        project_id: UUID,
        name: str,
        owner_id: UUID,
        plants: list[ImportedVersion],
        cases: list[ImportedCase],
    ) -> Project:
        """Create a project with its plant and case versions in one transaction."""
        project = Project(id=project_id, name=name, owner_id=owner_id)
        self.session.add(project)
        await self.session.flush()
        self.session.add_all(
            PlantVersion(
                project_id=project.id,
                number=version.number,
                content=version.content,
                digest=content_digest(version.content),
                note=version.note,
                author_id=owner_id,
                created=version.created,
            )
            for version in plants
        )
        for case in cases:
            await self.add_case(project.id, owner_id, case)
        await self.session.commit()
        return await self.get_by_id(project.id)

    async def add_case(
        self,
        project_id: UUID,
        owner_id: UUID,
        case: ImportedCase,
    ) -> None:
        version = CaseVersion(
            id=uuid4(),
            project_id=project_id,
            number=case.number,
            content=case.content,
            missing=case.missing,
            digest=content_digest(case.content),
            note=case.note,
            author_id=owner_id,
            created=case.created,
        )
        self.session.add(version)
        await self.session.flush()
        self.session.add_all(
            CaseFile(
                project_id=project_id,
                case_version_id=version.id,
                name=file.name,
                size=file.size,
                object_key=file.object_key,
            )
            for file in case.files
        )

    async def delete(self, project_id: UUID) -> None:
        await self.session.execute(delete(Project).where(Project.id == project_id))
        await self.session.commit()


def get_project_repository(session: DatabaseSession) -> ProjectRepository:
    return ProjectRepository(session)
