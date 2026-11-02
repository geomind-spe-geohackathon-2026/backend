from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update

from src.core.clients.postgres.models.run import (
    ACTIVE_RUN_STATUSES,
    FINISHED_STATUSES,
    Run,
)
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.pagination.page import PageRequest


class RunRepository(BaseRepository):
    async def create(
        self,
        run_id: UUID,
        chat_id: UUID,
        project_id: UUID,
        author_id: UUID,
    ) -> Run:
        """Add a queued run under the id geomind will use for it."""
        run = Run(
            id=run_id,
            chat_id=chat_id,
            project_id=project_id,
            author_id=author_id,
            status="queued",
        )
        self.session.add(run)
        await self.session.commit()
        return run

    async def get_by_id(self, run_id: UUID) -> Run | None:
        return await self.session.get(Run, run_id)

    async def update(self, run: Run, values: dict[str, Any]) -> Run:
        for name, value in values.items():
            setattr(run, name, value)
        await self.session.commit()
        return run

    async def claim(
        self,
        run_id: UUID,
        expected: str,
        values: dict[str, Any],
    ) -> bool:
        """Change a run only while it has the ``expected`` status; say whether it did.

        Two requests that race for the same run cannot both win.
        """
        statement = (
            update(Run).where(Run.id == run_id, Run.status == expected).values(**values)
        )
        result = await self.session.execute(statement)
        await self.session.commit()
        return result.rowcount == 1

    async def list_page(
        self,
        project_id: UUID,
        page: PageRequest,
        active_only: bool = False,
    ) -> list[Run]:
        """List runs, newest first."""
        statement = select(Run).where(Run.project_id == project_id)
        if active_only:
            statement = statement.where(Run.status.in_(ACTIVE_RUN_STATUSES))
        statement = statement.order_by(Run.created.desc(), Run.id.desc())
        statement = statement.limit(page.limit + 1)
        if page.after is not None:
            after_created, after_id = page.after
            statement = statement.where(
                (Run.created < after_created)
                | ((Run.created == after_created) & (Run.id < after_id))
            )
        return list(await self.session.scalars(statement))

    async def last_for_chats(self, chat_ids: list[UUID]) -> dict[UUID, Run]:
        """Return the newest run of each chat that has one."""
        statement = (
            select(Run).where(Run.chat_id.in_(chat_ids)).order_by(Run.created, Run.id)
        )
        runs = await self.session.scalars(statement)
        return {run.chat_id: run for run in runs}

    async def has_active(self, chat_id: UUID) -> bool:
        statement = select(Run.id).where(
            Run.chat_id == chat_id,
            Run.status.in_(ACTIVE_RUN_STATUSES),
        )
        return await self.session.scalar(statement.limit(1)) is not None

    async def usage(self, project_id: UUID) -> tuple[int, int, int, float]:
        """Return run count, input tokens, output tokens and cost of a project."""
        statement = select(
            func.count(Run.id),
            func.coalesce(func.sum(Run.input_tokens), 0),
            func.coalesce(func.sum(Run.output_tokens), 0),
            func.coalesce(func.sum(Run.cost), 0.0),
        ).where(Run.project_id == project_id)
        row = (await self.session.execute(statement)).one()
        return row[0], int(row[1]), int(row[2]), float(row[3])

    async def finished_usage(self, project_id: UUID) -> tuple[int, int, float]:
        """Return input tokens, output tokens and cost of the finished runs."""
        statement = select(
            func.coalesce(func.sum(Run.input_tokens), 0),
            func.coalesce(func.sum(Run.output_tokens), 0),
            func.coalesce(func.sum(Run.cost), 0.0),
        ).where(Run.project_id == project_id, Run.status.in_(FINISHED_STATUSES))
        row = (await self.session.execute(statement)).one()
        return int(row[0]), int(row[1]), float(row[2])


def get_run_repository(session: DatabaseSession) -> RunRepository:
    return RunRepository(session)
