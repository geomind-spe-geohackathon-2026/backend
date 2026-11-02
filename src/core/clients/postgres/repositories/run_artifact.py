from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.core.clients.postgres.models.run_artifact import RunArtifact
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession


class RunArtifactRepository(BaseRepository):
    async def save(
        self,
        run_id: UUID,
        chat_id: UUID,
        key: str,
        data: bytes | Any,
    ) -> RunArtifact:
        """Save bytes or a JSON value; a later save under the same key wins."""
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
            .where(RunArtifact.chat_id == chat_id, RunArtifact.key == key)
            .order_by(RunArtifact.created.desc(), RunArtifact.id.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)


def get_run_artifact_repository(session: DatabaseSession) -> RunArtifactRepository:
    return RunArtifactRepository(session)
