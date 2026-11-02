from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Select, func, select

from src.core.clients.postgres.models.activity import Activity
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.models.study import Study
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.routes import REPORT_ROUTE


@dataclass(frozen=True, slots=True)
class ProjectFacts:
    """What the progress of one project is computed from."""

    case_version: int | None = None
    case_missing: int = 0
    plant_version: int | None = None
    studies: dict[str, int] = field(default_factory=dict)
    results: int = 0
    reported: bool = False


class ProgressRepository(BaseRepository):
    """Read-only counts over the tables of other features."""

    async def grouped(self, statement: Select) -> dict[UUID, int]:
        rows = await self.session.execute(statement)
        return {row[0]: row[1] for row in rows}

    async def study_counts(
        self,
        project_ids: list[UUID],
    ) -> dict[UUID, dict[str, int]]:
        statement = (
            select(Study.project_id, Study.status, func.count(Study.id))
            .where(Study.project_id.in_(project_ids))
            .group_by(Study.project_id, Study.status)
        )
        counts: dict[UUID, dict[str, int]] = {}
        for project_id, status, count in await self.session.execute(statement):
            counts.setdefault(project_id, {})[status] = count
        return counts

    async def latest_cases(
        self, project_ids: list[UUID]
    ) -> dict[UUID, tuple[int, int]]:
        """Return the latest case number and its missing count for each project."""
        latest = (
            select(
                CaseVersion.project_id.label("project_id"),
                func.max(CaseVersion.number).label("number"),
            )
            .where(CaseVersion.project_id.in_(project_ids))
            .group_by(CaseVersion.project_id)
            .subquery()
        )
        statement = select(
            CaseVersion.project_id, CaseVersion.number, CaseVersion.missing
        ).join(
            latest,
            (CaseVersion.project_id == latest.c.project_id)
            & (CaseVersion.number == latest.c.number),
        )
        rows = await self.session.execute(statement)
        return {row[0]: (row[1], row[2]) for row in rows}

    async def facts(self, project_ids: list[UUID]) -> dict[UUID, ProjectFacts]:
        """Return the facts of each project, empty ones included."""
        case = await self.latest_cases(project_ids)
        plant = await self.grouped(
            select(PlantVersion.project_id, func.max(PlantVersion.number))
            .where(PlantVersion.project_id.in_(project_ids))
            .group_by(PlantVersion.project_id)
        )
        results = await self.grouped(
            select(Result.project_id, func.count(Result.id))
            .where(Result.project_id.in_(project_ids))
            .group_by(Result.project_id)
        )
        reported = await self.grouped(
            select(Activity.project_id, func.count(Activity.id))
            .where(
                Activity.project_id.in_(project_ids),
                Activity.link_route == REPORT_ROUTE,
            )
            .group_by(Activity.project_id)
        )
        studies = await self.study_counts(project_ids)
        return {
            project_id: ProjectFacts(
                case_version=case[project_id][0] if project_id in case else None,
                case_missing=case[project_id][1] if project_id in case else 0,
                plant_version=plant.get(project_id),
                studies=studies.get(project_id, {}),
                results=results.get(project_id, 0),
                reported=project_id in reported,
            )
            for project_id in project_ids
        }


def get_progress_repository(session: DatabaseSession) -> ProgressRepository:
    return ProgressRepository(session)
