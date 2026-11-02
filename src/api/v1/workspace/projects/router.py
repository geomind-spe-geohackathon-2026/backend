from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status
from src.api.v1.workspace.projects import schemas, services
from src.core.clients.minio.blobs import BlobStoreDependency
from src.core.clients.postgres.repositories.case_file import (
    CaseFileRepository,
    get_case_file_repository,
)
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
    get_case_version_repository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
    get_plant_version_repository,
)
from src.core.clients.postgres.repositories.progress import (
    ProgressRepository,
    get_progress_repository,
)
from src.core.clients.postgres.repositories.project import (
    ProjectRepository,
    get_project_repository,
)
from src.core.pagination.page import Page, PageParams
from src.core.security.access import AccessibleProject, CurrentUser

router = APIRouter(prefix="/projects", tags=["Projects"])

CaseFileRepositoryDependency = Annotated[
    CaseFileRepository,
    Depends(get_case_file_repository),
]
CaseVersionRepositoryDependency = Annotated[
    CaseVersionRepository,
    Depends(get_case_version_repository),
]
PlantVersionRepositoryDependency = Annotated[
    PlantVersionRepository,
    Depends(get_plant_version_repository),
]
ProgressRepositoryDependency = Annotated[
    ProgressRepository,
    Depends(get_progress_repository),
]
ProjectRepositoryDependency = Annotated[
    ProjectRepository,
    Depends(get_project_repository),
]


@router.get("", response_model=Page[schemas.Project])
async def list_projects(
    user: CurrentUser,
    page: PageParams,
    repository: ProjectRepositoryDependency,
    progress: ProgressRepositoryDependency,
    search: Annotated[str | None, Query()] = None,
) -> Page:
    return await services.list_projects(user, page, search, repository, progress)


@router.post(
    "",
    response_model=schemas.Project,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: schemas.ProjectCreate,
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
    progress: ProgressRepositoryDependency,
) -> schemas.Project:
    return await services.create_project(payload, user, repository, progress)


@router.post(
    "/import",
    response_model=schemas.Project,
    status_code=status.HTTP_201_CREATED,
)
async def import_project(
    file: UploadFile,
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
    progress: ProgressRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.Project:
    return await services.import_project(file, user, repository, progress, blobs)


@router.get("/{project_id}", response_model=schemas.Project)
async def get_project(
    project: AccessibleProject,
    progress: ProgressRepositoryDependency,
) -> schemas.Project:
    return await services.get_project(project, progress)


@router.patch("/{project_id}", response_model=schemas.Project)
async def rename_project(
    payload: schemas.ProjectUpdate,
    project: AccessibleProject,
    repository: ProjectRepositoryDependency,
    progress: ProgressRepositoryDependency,
) -> schemas.Project:
    return await services.rename_project(project, payload, repository, progress)


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
    plants: PlantVersionRepositoryDependency,
    cases: CaseVersionRepositoryDependency,
    files: CaseFileRepositoryDependency,
    blobs: BlobStoreDependency,
) -> Response:
    archive = await services.export_project(project, plants, cases, files, blobs)
    filename = f"project-{project.id}.zip"
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
