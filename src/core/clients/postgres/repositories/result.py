from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.pagination.page import PageRequest, paginate


class ResultRepository(BaseRepository):
    async def create(self, values: dict[str, Any]) -> Result:
        result = Result(**values)
        self.session.add(result)
        await self.session.commit()
        return result

    async def get_by_id(self, result_id: UUID) -> Result | None:
        return await self.session.get(Result, result_id)

    async def get_for_study(self, study_id: UUID) -> Result | None:
        statement = select(Result).where(Result.study_id == study_id).limit(1)
        return await self.session.scalar(statement)

    async def by_ids(self, project_id: UUID, result_ids: list[UUID]) -> list[Result]:
        statement = select(Result).where(
            Result.project_id == project_id,
            Result.id.in_(result_ids),
        )
        return list(await self.session.scalars(statement))

    async def list_page(self, project_id: UUID, page: PageRequest) -> list[Result]:
        statement = select(Result).where(Result.project_id == project_id)
        statement = paginate(statement, Result.created, Result.id, page)
        return list(await self.session.scalars(statement))


def get_result_repository(session: DatabaseSession) -> ResultRepository:
    return ResultRepository(session)
