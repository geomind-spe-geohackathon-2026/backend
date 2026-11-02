from datetime import datetime
from typing import NoReturn

from src.api.v1.plant.parameters import schemas
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.errors import NotImplementedYetError
from src.core.gemini import plant
from src.core.gemini.errors import PlantNotFoundError
from src.core.versioning import (
    Version,
    check_base,
    describe_versions,
    latest_version,
)

CATALOGUE_NAME = "plant.catalogue"


async def get_parameters(
    project: Project,
    module: str,
    at: datetime | None,
    repository: PlantVersionRepository,
) -> schemas.Parameters:
    """Return a module's parameters in the latest plant, valid at a time."""
    latest = await latest_version(repository, project.id, PlantNotFoundError)
    built = plant.from_dict(latest.content)
    return schemas.Parameters(**plant.parameters(built, module, at))


async def save_parameters(
    project: Project,
    payload: schemas.ParametersUpdate,
    user: User,
    repository: PlantVersionRepository,
    activity: ActivityRepository,
    users: UserRepository,
) -> Version:
    """Save a new plant version with the module's parameters changed."""
    latest = await latest_version(repository, project.id, PlantNotFoundError)
    check_base(latest, payload.base)
    built = plant.from_dict(latest.content)
    plant.set_parameters(built, payload.module, payload.params, payload.valid_from)
    version = await repository.save_version(
        project.id, plant.to_dict(built), payload.note, user.id
    )
    await activity.add(
        project.id,
        "user",
        user.name,
        f"Changed {payload.module} in plant version {version.number}",
        "design/plant",
        str(version.number),
    )
    return (await describe_versions([version], users))[0]


def fill_parameters() -> NoReturn:
    """Refuse: filling from a catalogue entry needs the unbuilt catalogue."""
    raise NotImplementedYetError(CATALOGUE_NAME)
