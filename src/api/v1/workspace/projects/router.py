from typing import Annotated

from fastapi import APIRouter, Depends, status
from src.api.v1.workspace.projects import schemas, services
from src.core.clients.postgres.repositories.project import (
    ProjectRepository,
    get_project_repository,
)
from src.core.pagination.page import Page, PageParams
from src.core.security.access import AccessibleProject, CurrentUser

router = APIRouter(prefix="/projects", tags=["Projects"])

ProjectRepositoryDependency = Annotated[
    ProjectRepository,
    Depends(get_project_repository),
]


@router.get("", response_model=Page[schemas.ProjectResponse])
async def list_projects(
    user: CurrentUser,
    page: PageParams,
    repository: ProjectRepositoryDependency,
) -> Page:
    return await services.list_projects(user, page, repository)


@router.post(
    "",
    response_model=schemas.ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: schemas.ProjectCreate,
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
) -> schemas.ProjectResponse:
    return await services.create_project(payload, user, repository)


@router.get("/{project_id}", response_model=schemas.ProjectResponse)
async def get_project(project: AccessibleProject) -> schemas.ProjectResponse:
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project: AccessibleProject,
    repository: ProjectRepositoryDependency,
) -> None:
    await services.delete_project(project, repository)
