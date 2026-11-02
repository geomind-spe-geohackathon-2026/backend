import mimetypes
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Response, UploadFile, status
from src.api.v1.design.case import schemas, services
from src.core.clients.minio.blobs import BlobStoreDependency
from src.core.clients.postgres.repositories.activity import (
    ActivityRepository,
    get_activity_repository,
)
from src.core.clients.postgres.repositories.case_file import (
    CaseFileRepository,
    get_case_file_repository,
)
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
    get_case_version_repository,
)
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.pagination.page import Page
from src.core.security.access import (
    CurrentUser,
    ProjectRepositoryDependency,
    QueriedProject,
    require_project,
)
from src.core.uploads import read_upload
from src.core.versioning import Version

router = APIRouter(prefix="/case", tags=["Case"])

CaseVersionRepositoryDependency = Annotated[
    CaseVersionRepository,
    Depends(get_case_version_repository),
]
CaseFileRepositoryDependency = Annotated[
    CaseFileRepository,
    Depends(get_case_file_repository),
]
ActivityRepositoryDependency = Annotated[
    ActivityRepository,
    Depends(get_activity_repository),
]
UserRepositoryDependency = Annotated[UserRepository, Depends(get_user_repository)]


@router.get("", response_model=schemas.Case)
async def get_case(
    project: QueriedProject,
    repository: CaseVersionRepositoryDependency,
    files: CaseFileRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.Case:
    return await services.get_case(project, repository, files, blobs)


@router.get("/schema")
async def get_schema(_user: CurrentUser) -> dict:
    return services.case_schema()


@router.post("", response_model=schemas.Case, status_code=status.HTTP_201_CREATED)
async def save_case(
    payload: schemas.CaseCreate,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    repository: CaseVersionRepositoryDependency,
    files: CaseFileRepositoryDependency,
    activity: ActivityRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.Case:
    project = await require_project(payload.project, user, projects)
    return await services.save_case(
        project, payload, user, repository, files, activity, blobs
    )


@router.post("/validate", response_model=schemas.CaseProblems)
async def validate_case(
    payload: schemas.CaseCheck,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    repository: CaseVersionRepositoryDependency,
    files: CaseFileRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.CaseProblems:
    stored: dict[str, bytes] | None = None
    if payload.project is not None:
        project = await require_project(payload.project, user, projects)
        stored = await services.saved_files(project, repository, files, blobs)
    return services.check_case(payload.content, stored)


@router.post("/files", response_model=schemas.Case, status_code=status.HTTP_201_CREATED)
async def add_file(
    project: Annotated[UUID, Form()],
    name: Annotated[str, Form()],
    file: UploadFile,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    repository: CaseVersionRepositoryDependency,
    files: CaseFileRepositoryDependency,
    activity: ActivityRepositoryDependency,
    blobs: BlobStoreDependency,
    base: Annotated[int | None, Form()] = None,
) -> schemas.Case:
    accessible = await require_project(project, user, projects)
    return await services.add_file(
        accessible,
        base,
        name,
        await read_upload(file),
        user,
        repository,
        files,
        activity,
        blobs,
    )


@router.get("/files/{name:path}", response_class=Response)
async def get_file(
    name: str,
    project: QueriedProject,
    repository: CaseVersionRepositoryDependency,
    files: CaseFileRepositoryDependency,
    blobs: BlobStoreDependency,
    version: int | None = None,
) -> Response:
    data = await services.get_file(project, name, version, repository, files, blobs)
    media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return Response(content=data, media_type=media_type)


@router.get("/series", response_model=schemas.SeriesList)
async def get_series(
    project: QueriedProject,
    repository: CaseVersionRepositoryDependency,
    files: CaseFileRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.SeriesList:
    return await services.get_series(project, repository, files, blobs)


@router.get("/versions", response_model=Page[Version])
async def list_versions(
    project: QueriedProject,
    repository: CaseVersionRepositoryDependency,
    users: UserRepositoryDependency,
) -> Page[Version]:
    return await services.list_versions(project, repository, users)
