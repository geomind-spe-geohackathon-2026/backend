from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select

from src.core.clients.postgres.models.case_version import CaseVersion
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

    async def economics(self, project_ids: list[UUID]) -> dict[UUID, bool]:
        """Return whether each project's latest case version has economics (QA-194)."""
        return await has_economics(self.progress.session, project_ids)


async def has_economics(session: Any, project_ids: list[UUID]) -> dict[UUID, bool]:
    """Return, per project, whether its latest case has a non-empty ``economics`` section.

    A project without a case is ``False``.
    """
    found = dict.fromkeys(project_ids, False)
    if not project_ids:
        return found
    newest = (
        select(CaseVersion.project_id, func.max(CaseVersion.number).label("number"))
        .where(CaseVersion.project_id.in_(project_ids))
        .group_by(CaseVersion.project_id)
        .subquery()
    )
    statement = select(CaseVersion.project_id, CaseVersion.content).join(
        newest,
        (CaseVersion.project_id == newest.c.project_id)
        & (CaseVersion.number == newest.c.number),
    )
    for project_id, content in await session.execute(statement):
        economics = content.get("economics") if isinstance(content, dict) else None
        found[project_id] = bool(economics)
    return found


def get_progress_reader(session: DatabaseSession) -> ProgressReader:
    return ProgressReader(ProgressRepository(session))


ProgressReaderDependency = Annotated[ProgressReader, Depends(get_progress_reader)]
