from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.core.clients.postgres.models.study import ACTIVE_STUDY_STATUSES, Study
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.pagination.page import PageRequest, paginate


class StudyRepository(BaseRepository):
    async def create(self, values: dict[str, Any]) -> Study:
        study = Study(**values)
        self.session.add(study)
        await self.session.commit()
        return study

    async def get_by_id(self, study_id: UUID) -> Study | None:
        return await self.session.get(Study, study_id)

    async def update(self, study: Study, values: dict[str, Any]) -> Study:
        for name, value in values.items():
            setattr(study, name, value)
        await self.session.commit()
        return study

    async def refresh(self, study: Study) -> Study:
        await self.session.refresh(study)
        return study

    async def list_page(self, project_id: UUID, page: PageRequest) -> list[Study]:
        statement = select(Study).where(Study.project_id == project_id)
        statement = paginate(statement, Study.created, Study.id, page)
        return list(await self.session.scalars(statement))

    async def has_active(self, project_id: UUID) -> bool:
        statement = select(Study.id).where(
            Study.project_id == project_id,
            Study.status.in_(ACTIVE_STUDY_STATUSES),
        )
        return await self.session.scalar(statement.limit(1)) is not None


def get_study_repository(session: DatabaseSession) -> StudyRepository:
    return StudyRepository(session)
