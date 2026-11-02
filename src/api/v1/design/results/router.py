from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from src.api.v1.design.results import schemas, services
from src.core.clients.postgres.repositories.project import (
    ProjectRepository,
    get_project_repository,
)
from src.core.clients.postgres.repositories.result import (
    ResultRepository,
    get_result_repository,
)
from src.core.pagination.page import Page, PageParams
from src.core.security.access import CurrentUser

router = APIRouter(prefix="/results", tags=["Results"])

ProjectRepositoryDependency = Annotated[
    ProjectRepository,
    Depends(get_project_repository),
]
ResultRepositoryDependency = Annotated[
    ResultRepository,
    Depends(get_result_repository),
]


@router.get("", response_model=Page[schemas.Result])
async def list_results(
    project: UUID,
    user: CurrentUser,
    page: PageParams,
    projects: ProjectRepositoryDependency,
    results: ResultRepositoryDependency,
) -> Page:
    return await services.list_results(project, user, page, projects, results)


@router.get("/compare", response_model=schemas.ResultComparison)
async def compare_results(
    project: UUID,
    ids: str,
    x: str,
    y: str,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    results: ResultRepositoryDependency,
) -> schemas.ResultComparison:
    return await services.compare_results(project, ids, x, y, user, projects, results)


@router.get("/{result_id}", response_model=schemas.ResultDetail)
async def get_result(
    result_id: UUID,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    results: ResultRepositoryDependency,
) -> schemas.ResultDetail:
    return await services.get_result(result_id, user, projects, results)
