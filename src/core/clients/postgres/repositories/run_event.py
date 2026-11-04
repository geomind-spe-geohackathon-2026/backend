from typing import Any
from uuid import UUID

from sqlalchemy import or_, select

from src.core.clients.postgres.models.run_event import RunEvent
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession


class RunEventRepository(BaseRepository):
    async def add(
        self,
        run_id: UUID,
        sequence: int,
        event_type: str,
        public: bool,
        data: dict[str, Any],
    ) -> RunEvent:
        event = RunEvent(
            run_id=run_id,
            sequence=sequence,
            type=event_type,
            public=public,
            data=data,
        )
        self.session.add(event)
        await self.session.commit()
        return event

    async def after(
        self,
        run_id: UUID,
        sequence: int,
        public_only: bool = False,
        also: tuple[str, ...] = (),
    ) -> list[RunEvent]:
        """Return a run's events above ``sequence``; ``also`` adds internal types."""
        statement = select(RunEvent).where(
            RunEvent.run_id == run_id,
            RunEvent.sequence > sequence,
        )
        if public_only:
            statement = statement.where(
                or_(RunEvent.public.is_(True), RunEvent.type.in_(also))
            )
        statement = statement.order_by(RunEvent.sequence, RunEvent.id)
        return list(await self.session.scalars(statement))

    async def of_type(self, run_id: UUID, event_type: str) -> list[RunEvent]:
        """Return a run's events of one type, the newest first."""
        statement = (
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.type == event_type)
            .order_by(RunEvent.sequence.desc(), RunEvent.id.desc())
        )
        return list(await self.session.scalars(statement))


def get_run_event_repository(session: DatabaseSession) -> RunEventRepository:
    return RunEventRepository(session)
