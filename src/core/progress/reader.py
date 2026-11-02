from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from src.core.clients.postgres.repositories.base import DatabaseSession
from src.core.clients.postgres.repositories.progress import (
    ProgressRepository,
    ProjectFacts,
)


@dataclass(frozen=True, slots=True)
class ProgressReader:
    """The facts progress is computed from; a case stores its missing count."""

    progress: ProgressRepository

    async def facts(self, project_ids: list[UUID]) -> dict[UUID, ProjectFacts]:
        """Return the facts of each project, empty ones included."""
        return await self.progress.facts(project_ids)


def get_progress_reader(session: DatabaseSession) -> ProgressReader:
    return ProgressReader(ProgressRepository(session))


ProgressReaderDependency = Annotated[ProgressReader, Depends(get_progress_reader)]
