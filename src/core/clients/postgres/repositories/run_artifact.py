from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.core.clients.postgres.models.run_artifact import RunArtifact
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession


class RunArtifactRepository(BaseRepository):
    async def save(
        self,
        run_id: UUID | None,
        chat_id: UUID,
        key: str,
        data: bytes | Any,
    ) -> RunArtifact:
        """Save bytes or a JSON value; no run id means the chat's space."""
        if isinstance(data, bytes):
            artifact = RunArtifact(
                run_id=run_id,
                chat_id=chat_id,
                key=key,
                kind="bytes",
                data_bytes=data,
            )
        else:
            artifact = RunArtifact(
                run_id=run_id,
                chat_id=chat_id,
                key=key,
                kind="json",
                data_json=data,
            )
        self.session.add(artifact)
        await self.session.commit()
        return artifact

    async def newest_for_run(self, run_id: UUID, key: str) -> RunArtifact | None:
        statement = (
            select(RunArtifact)
            .where(RunArtifact.run_id == run_id, RunArtifact.key == key)
            .order_by(RunArtifact.created.desc(), RunArtifact.id.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def newest_for_chat(self, chat_id: UUID, key: str) -> RunArtifact | None:
        statement = (
            select(RunArtifact)
            .where(
                RunArtifact.chat_id == chat_id,
                RunArtifact.run_id.is_(None),
                RunArtifact.key == key,
            )
            .order_by(RunArtifact.created.desc(), RunArtifact.id.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def all_for_chat(self, chat_id: UUID) -> dict[str, Any]:
        """Return the newest value of every key of a chat's own space."""
        statement = (
            select(RunArtifact)
            .where(RunArtifact.chat_id == chat_id, RunArtifact.run_id.is_(None))
            .order_by(RunArtifact.created, RunArtifact.id)
        )
        rows = await self.session.scalars(statement)
        return {row.key: row.data for row in rows}


def get_run_artifact_repository(session: DatabaseSession) -> RunArtifactRepository:
    return RunArtifactRepository(session)
