from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from src.api.v1.plant.flowsheet import schemas, services
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
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
    get_plant_version_repository,
)
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.gemini.stored import latest_case
from src.core.pagination.page import Page
from src.core.security.access import (
    CurrentUser,
    ProjectRepositoryDependency,
    QueriedProject,
    require_project,
)
from src.core.versioning import Version

router = APIRouter(prefix="/flowsheet", tags=["Flowsheet"])

PlantVersionRepositoryDependency = Annotated[
    PlantVersionRepository,
    Depends(get_plant_version_repository),
]
ActivityRepositoryDependency = Annotated[
    ActivityRepository,
    Depends(get_activity_repository),
]
UserRepositoryDependency = Annotated[UserRepository, Depends(get_user_repository)]
CaseVersionRepositoryDependency = Annotated[
    CaseVersionRepository,
    Depends(get_case_version_repository),
]
CaseFileRepositoryDependency = Annotated[
    CaseFileRepository,
    Depends(get_case_file_repository),
]


@router.get("/palette", response_model=list[schemas.Palette])
async def list_palette(
    _user: CurrentUser,
    category: Annotated[str | None, Query()] = None,
) -> list[schemas.Palette]:
    return services.list_palette(category)


@router.get("/ports", response_model=list[schemas.ModulePorts])
async def list_ports(_user: CurrentUser) -> list[schemas.ModulePorts]:
    return services.list_ports()


@router.get("/templates", response_model=list[schemas.Template])
async def list_templates(_user: CurrentUser) -> list[schemas.Template]:
    return services.list_templates()


@router.get("", response_model=schemas.Flowsheet)
async def get_flowsheet(
    project: QueriedProject,
    repository: PlantVersionRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.Flowsheet:
    return await services.get_flowsheet(project, None, repository, blobs)


@router.post(
    "",
    response_model=schemas.Flowsheet,
    status_code=status.HTTP_201_CREATED,
)
async def save_flowsheet(
    payload: schemas.FlowsheetCreate,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    repository: PlantVersionRepositoryDependency,
    activity: ActivityRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.Flowsheet:
    project = await require_project(payload.project, user, projects)
    return await services.save_flowsheet(
        project, payload, user, repository, activity, blobs
    )


@router.put("/layout", response_model=schemas.Flowsheet)
async def save_layout(
    payload: schemas.LayoutUpdate,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    repository: PlantVersionRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.Flowsheet:
    project = await require_project(payload.project, user, projects)
    return await services.save_layout(project, payload, repository, blobs)


@router.post("/validate", response_model=schemas.SpecProblems)
async def validate_spec(
    payload: schemas.SpecCheck,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    cases: CaseVersionRepositoryDependency,
    files: CaseFileRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.SpecProblems:
    built = None
    if payload.project is not None:
        project = await require_project(payload.project, user, projects)
        built = await latest_case(project.id, cases, files, blobs)
    return await services.validate_spec(payload.spec, built)


@router.get("/versions", response_model=Page[Version])
async def list_versions(
    project: QueriedProject,
    repository: PlantVersionRepositoryDependency,
    users: UserRepositoryDependency,
) -> Page[Version]:
    return await services.list_versions(project, repository, users)


@router.get("/versions/{number}", response_model=schemas.Flowsheet)
async def get_version(
    number: int,
    project: QueriedProject,
    repository: PlantVersionRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.Flowsheet:
    return await services.get_flowsheet(project, number, repository, blobs)
