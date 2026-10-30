from typing import Annotated

from fastapi import APIRouter, Depends, Response, UploadFile, status
from src.api.v1.workspace.projects import schemas, services
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
    get_plant_version_repository,
)
from src.core.clients.postgres.repositories.project import (
    ProjectRepository,
    get_project_repository,
)
from src.core.pagination.page import Page, PageParams
from src.core.security.access import AccessibleProject, CurrentUser

router = APIRouter(prefix="/projects", tags=["Projects"])

PlantVersionRepositoryDependency = Annotated[
    PlantVersionRepository,
    Depends(get_plant_version_repository),
]
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


@router.post(
    "/import",
    response_model=schemas.ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_project(
    file: UploadFile,
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
) -> schemas.ProjectResponse:
    return await services.import_project(file, user, repository)


@router.get("/{project_id}", response_model=schemas.ProjectResponse)
async def get_project(project: AccessibleProject) -> schemas.ProjectResponse:
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project: AccessibleProject,
    repository: ProjectRepositoryDependency,
) -> None:
    await services.delete_project(project, repository)


@router.get(
    "/{project_id}/export",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}}},
)
async def export_project(
    project: AccessibleProject,
    repository: PlantVersionRepositoryDependency,
) -> Response:
    archive = await services.export_project(project, repository)
    filename = f"project-{project.id}.zip"
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
