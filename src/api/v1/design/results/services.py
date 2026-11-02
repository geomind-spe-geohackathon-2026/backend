from typing import Any
from uuid import UUID

from src.api.v1.design.results import errors, schemas
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.errors import ValidationFailedError
from src.core.gemini import evaluate as gemini_evaluate
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
    }


def to_detail(result: Result) -> schemas.ResultDetail:
    content = result.content
    parts = gemini_evaluate.summarise(content["report"])
    return schemas.ResultDetail(
        **to_summary(result),
        capacities=parts["capacities"],
        sizes=parts["sizes"],
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


async def get_result(
    result_id: UUID,
    user: User,
    projects: ProjectRepository,
    results: ResultRepository,
) -> schemas.ResultDetail:
    result = await results.get_by_id(result_id)
    if result is None:
        raise errors.ResultNotFoundError("Result not found")
    try:
        await require_project(result.project_id, user, projects)
    except ProjectNotFoundError as error:
        raise errors.ResultNotFoundError("Result not found") from error
    return to_detail(result)


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
    )
