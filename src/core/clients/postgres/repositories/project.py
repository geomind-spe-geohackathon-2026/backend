from typing import Annotated
from uuid import UUID

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from src.core.clients.postgres.client import get_db
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.repositories.base import BaseRepository
from src.core.pagination.page import PageRequest, paginate

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


class ProjectRepository(BaseRepository):
    def select_projects(self) -> Select:
        return select(Project).execution_options(populate_existing=True)

    async def get_by_id(self, project_id: UUID) -> Project | None:
        statement = self.select_projects().where(Project.id == project_id)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        page: PageRequest,
        owner_id: UUID | None = None,
    ) -> list[Project]:
        statement = self.select_projects()
        if owner_id is not None:
            statement = statement.where(Project.owner_id == owner_id)
        statement = paginate(statement, Project.created, Project.id, page)
        return list(await self.session.scalars(statement))

    async def create(self, name: str, owner_id: UUID) -> Project:
        project = Project(name=name, owner_id=owner_id)
        self.session.add(project)
        await self.session.commit()
        return await self.get_by_id(project.id)

    async def delete(self, project_id: UUID) -> None:
        await self.session.execute(delete(Project).where(Project.id == project_id))
        await self.session.commit()


def get_project_repository(session: DatabaseSession) -> ProjectRepository:
    return ProjectRepository(session)
