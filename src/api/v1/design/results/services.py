import asyncio
from typing import Any
from uuid import UUID

from src.api.v1.design.results import errors, schemas
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.errors import ValidationFailedError
from src.core.gemini import evaluate as gemini_evaluate
from src.core.gemini import study as gemini_study
from src.core.gemini.stored import stored_files
from src.core.pagination.page import Page, PageRequest, encode_cursor
from src.core.security.access import require_project
from src.core.security.errors import ProjectNotFoundError


def to_summary(result: Result) -> dict[str, Any]:
    return {
        "id": result.id,
        "name": result.name,
        "study": result.study_id,
        "case_version": result.case_version,
        "plant_version": result.plant_version,
        "kpis": gemini_evaluate.kpis_of(result.content["report"]),
        "checks": result.summary["checks"],
        "created": result.created,
        "role": gemini_evaluate.role_of(result.content.get("run", {})),
        **gemini_evaluate.design_facts(result.content.get("design") or {}),
    }


def to_detail(
    result: Result,
    limits: dict[str, dict[str, Any]] | None = None,
) -> schemas.ResultDetail:
    content = result.content
    parts = gemini_evaluate.summarise(content["report"], limits)
    return schemas.ResultDetail(
        **to_summary(result),
        capacities=parts["capacities"],
        sizes=parts["sizes"],
        tornado=gemini_evaluate.tornado_of(content.get("run", {})),
        spread=gemini_evaluate.spread_of(content.get("run", {})),
        coverage=content.get("coverage"),
        constraints=parts["constraints"],
        series=content["series"],
    )


async def list_results(
    project_id: UUID,
    user: User,
    page: PageRequest,
    projects: ProjectRepository,
    results: ResultRepository,
) -> Page:
    project = await require_project(project_id, user, projects)
    rows = await results.list_page(project.id, page)
    items = rows[: page.limit]
    last = items[-1] if len(rows) > page.limit else None
    return Page(
        items=[schemas.Result(**to_summary(item)) for item in items],
        next=encode_cursor(last.created, last.id) if last else None,
    )


async def add_coverage(
    result: Result,
    case: CaseVersion,
    files: CaseFileRepository,
    blobs: BlobStore,
    results: ResultRepository,
) -> None:
    """Compute the coverage of a result stored before it existed, and keep it."""
    data = await stored_files(await files.list_for_version(case.id), blobs)
    coverage = await asyncio.to_thread(
        gemini_study.stored_coverage, result.content["design"], case.content, data
    )
    if coverage is not None:
        await results.set_content(result, {**result.content, "coverage": coverage})


async def readable_result(
    result_id: UUID,
    user: User,
    projects: ProjectRepository,
    results: ResultRepository,
) -> Result:
    result = await results.get_by_id(result_id)
    if result is None:
        raise errors.ResultNotFoundError("Result not found")
    try:
        await require_project(result.project_id, user, projects)
    except ProjectNotFoundError as error:
        raise errors.ResultNotFoundError("Result not found") from error
    return result


async def adopt_design(
    result_id: UUID,
    user: User,
    projects: ProjectRepository,
    results: ResultRepository,
    plants: PlantVersionRepository,
) -> schemas.AdoptedDesign:
    """Save the design of a result as the project's next plant version."""
    result = await readable_result(result_id, user, projects, results)
    note = f"Design of {result.name}"
    version = await plants.save_version(
        result.project_id, result.content["design"], note, user.id
    )
    return schemas.AdoptedDesign(plant_version=version.number)


async def get_result(
    result_id: UUID,
    user: User,
    projects: ProjectRepository,
    results: ResultRepository,
    cases: CaseVersionRepository,
    files: CaseFileRepository,
    blobs: BlobStore,
) -> schemas.ResultDetail:
    result = await readable_result(result_id, user, projects, results)
    case = await cases.version_by_number(result.project_id, result.case_version)
    if case is None:
        return to_detail(result)
    if result.content.get("coverage") is None and result.content.get("design"):
        await add_coverage(result, case, files, blobs, results)
    return to_detail(result, gemini_evaluate.case_limits(case.content))


def parse_ids(text: str) -> list[UUID]:
    try:
        ids = [UUID(part) for part in text.split(",")]
    except ValueError as error:
        raise ValidationFailedError(
            {"ids": "Expected result ids separated by commas"}
        ) from error
    return list(dict.fromkeys(ids))


def check_kpi(name: str, field: str, found: list[Result]) -> None:
    known = {kpi["name"] for item in found for kpi in item.summary["kpis"]}
    if name not in known:
        raise ValidationFailedError({field: "Unknown figure of these results"})


def design_spreads(
    found: list[Result], everything: list[Result]
) -> list[schemas.DesignSpread]:
    """Return the spread of each uncertainty study run on one of the given designs."""
    spreads = []
    for design in found:
        for other in everything:
            run = other.content.get("run", {})
            same = other.content.get("design") == design.content.get("design")
            if other.id != design.id and same:
                spreads += [
                    schemas.DesignSpread(
                        result=design.id,
                        uncertainty=other.id,
                        metric=row["name"],
                        p5=row["p5"],
                        p95=row["p95"],
                    )
                    for row in gemini_evaluate.spread_of(run) or []
                ]
    return spreads


async def compare_results(
    project_id: UUID,
    ids: str,
    x: str,
    y: str,
    user: User,
    projects: ProjectRepository,
    results: ResultRepository,
) -> schemas.ResultComparison:
    project = await require_project(project_id, user, projects)
    wanted = parse_ids(ids)
    rows = {row.id: row for row in await results.by_ids(project.id, wanted)}
    if set(rows) != set(wanted):
        raise errors.ResultNotFoundError("Result not found")
    found = [rows[result_id] for result_id in wanted]
    check_kpi(x, "x", found)
    check_kpi(y, "y", found)
    flags = gemini_evaluate.pareto_flags(
        [item.content["report"] for item in found], x, y
    )
    return schemas.ResultComparison(
        items=[to_summary(item) for item in found],
        pareto=[item.id for item, flag in zip(found, flags, strict=True) if flag],
        spreads=design_spreads(found, await results.all_for_project(project.id)),
    )
