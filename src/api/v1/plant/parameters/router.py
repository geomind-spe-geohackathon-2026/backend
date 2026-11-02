from typing import Annotated

from pydantic import AwareDatetime

from fastapi import APIRouter, Depends, Query, status
from src.api.v1.plant.parameters import schemas, services
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
from src.core.security.access import (
    CurrentUser,
    ProjectRepositoryDependency,
    QueriedProject,
    require_project,
)
from src.core.versioning import Version

router = APIRouter(prefix="/parameters", tags=["Parameters"])

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


@router.get("", response_model=schemas.Parameters)
async def get_parameters(
    project: QueriedProject,
    module: Annotated[str, Query(min_length=1)],
    repository: PlantVersionRepositoryDependency,
    cases: CaseVersionRepositoryDependency,
    files: CaseFileRepositoryDependency,
    blobs: BlobStoreDependency,
    at: Annotated[AwareDatetime | None, Query()] = None,
) -> schemas.Parameters:
    built = await latest_case(project.id, cases, files, blobs)
    return await services.get_parameters(project, module, at, repository, built)


@router.post("", response_model=Version, status_code=status.HTTP_201_CREATED)
async def save_parameters(
    payload: schemas.ParametersUpdate,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    repository: PlantVersionRepositoryDependency,
    activity: ActivityRepositoryDependency,
    users: UserRepositoryDependency,
) -> Version:
    project = await require_project(payload.project, user, projects)
    return await services.save_parameters(
        project, payload, user, repository, activity, users
    )


@router.get("/plant", response_model=schemas.PlantSearch)
async def get_plant_search(
    project: QueriedProject,
    repository: PlantVersionRepositoryDependency,
) -> schemas.PlantSearch:
    return await services.get_plant_search(project, repository)


@router.post("/plant", response_model=Version, status_code=status.HTTP_201_CREATED)
async def save_plant_ranges(
    payload: schemas.PlantRangesUpdate,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    repository: PlantVersionRepositoryDependency,
    activity: ActivityRepositoryDependency,
    users: UserRepositoryDependency,
) -> Version:
    project = await require_project(payload.project, user, projects)
    return await services.save_plant_ranges(
        project, payload, user, repository, activity, users
    )


@router.post("/fill", response_model=Version, status_code=status.HTTP_201_CREATED)
async def fill_parameters(
    payload: schemas.ParametersFill,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
) -> Version:
    await require_project(payload.project, user, projects)
    services.fill_parameters()
