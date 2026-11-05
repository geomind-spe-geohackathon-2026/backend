"""The project's plant versions and studies, read-only, for the agents (QA-122).

geomind's ``project_designs`` lists every saved plant version and every study of the project
with its result's KPIs and checks, and every result of the project newest first (QA-294: the
agents could not find a result made in another chat), beside the designs of the chat; ``plant_version`` opens one
saved plant so an agent can compare alternatives.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.models.study import Study
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.gemini import evaluate
from src.core.versioning import saved_by


def plant_entry(row: PlantVersion, latest: int) -> dict[str, Any]:
    name = row.content.get("name")
    return {
        "version": row.number,
        "name": name if isinstance(name, str) and name else None,
        "note": row.note,
        "by": saved_by(row.note),
        "created": row.created.isoformat(),
        "latest": row.number == latest,
    }


def result_entry(result: Result | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "id": str(result.id),
        "name": result.name,
        "role": evaluate.role_of(result.content.get("run") or {}),
        "plant_version": result.plant_version,
        "case_version": result.case_version,
        "kpis": evaluate.kpis_of(result.content.get("report") or {}),
        "checks": result.summary.get("checks"),
    }


def listed_result(result: Result) -> dict[str, Any]:
    """Return one project result with its creation time (QA-294)."""
    entry = result_entry(result) or {}
    return {**entry, "created": result.created.isoformat()}


def study_entry(study: Study, result: Result | None) -> dict[str, Any]:
    return {
        "id": str(study.id),
        "name": study.name,
        "kind": study.kind,
        "status": study.status,
        "created": study.created.isoformat(),
        "plant_version": study.plant_version,
        "case_version": study.case_version,
        "settings": study.settings,
        "result": result_entry(result),
    }


def newest_by_study(results: list[Result]) -> dict[UUID, Result]:
    found: dict[UUID, Result] = {}
    for result in sorted(results, key=lambda item: item.created):
        if result.study_id is not None:
            found[result.study_id] = result
    return found


async def read_designs(
    session: AsyncSession, project_id: UUID
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    """Return ``project_designs`` and every plant version's content by number."""
    plants = await PlantVersionRepository(session).all_versions(project_id)
    studies = await StudyRepository(session).all_for_project(project_id)
    every = await ResultRepository(session).all_for_project(project_id)
    results = newest_by_study(every)
    latest = plants[-1].number if plants else 0
    newest_first = sorted(every, key=lambda item: (item.created, str(item.id)), reverse=True)
    designs = {
        "plants": [plant_entry(row, latest) for row in plants],
        "studies": [study_entry(item, results.get(item.id)) for item in studies],
        "results": [listed_result(item) for item in newest_first],
    }
    return designs, {row.number: row.content for row in plants}
