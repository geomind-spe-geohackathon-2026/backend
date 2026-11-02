from uuid import UUID

from sqlalchemy import select

from src.core.clients.postgres.models.activity import Activity
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession


class ActivityRepository(BaseRepository):
    async def add(
        self,
        project_id: UUID,
        actor_kind: str,
        actor_name: str,
        text: str,
        link_route: str | None = None,
        link_id: str | None = None,
    ) -> Activity:
        activity = Activity(
            project_id=project_id,
            actor_kind=actor_kind,
            actor_name=actor_name,
            text=text,
            link_route=link_route,
            link_id=link_id,
        )
        self.session.add(activity)
        await self.session.commit()
        return activity

    async def latest(self, project_id: UUID, limit: int) -> list[Activity]:
        """Return the newest rows of a project, newest first."""
        statement = (
            select(Activity)
            .where(Activity.project_id == project_id)
            .order_by(Activity.created.desc(), Activity.id.desc())
            .limit(limit)
        )
        return list(await self.session.scalars(statement))


def get_activity_repository(session: DatabaseSession) -> ActivityRepository:
    return ActivityRepository(session)
