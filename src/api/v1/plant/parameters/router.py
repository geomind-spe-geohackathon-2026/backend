from typing import Annotated

from pydantic import AwareDatetime

from fastapi import APIRouter, Depends, Query, status
from src.api.v1.plant.parameters import schemas, services
from src.api.v1.plant.parameters.dependencies import QueriedProject
from src.core.clients.postgres.repositories.activity import (
    ActivityRepository,
    get_activity_repository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
    get_plant_version_repository,
)
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.security.access import (
    CurrentUser,
    ProjectRepositoryDependency,
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


@router.get("", response_model=schemas.Parameters)
async def get_parameters(
    project: QueriedProject,
    module: Annotated[str, Query(min_length=1)],
    repository: PlantVersionRepositoryDependency,
    at: Annotated[AwareDatetime | None, Query()] = None,
) -> schemas.Parameters:
    return await services.get_parameters(project, module, at, repository)


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


@router.post("/fill", response_model=Version, status_code=status.HTTP_201_CREATED)
async def fill_parameters(
    payload: schemas.ParametersFill,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
) -> Version:
    await require_project(payload.project, user, projects)
    services.fill_parameters()
