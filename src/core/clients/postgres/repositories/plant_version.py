from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.repositories.base import DatabaseSession
from src.core.clients.postgres.repositories.version import (
    VersionRepository,
    content_digest,
)

__all__ = ["PlantVersionRepository", "content_digest", "get_plant_version_repository"]


class PlantVersionRepository(VersionRepository):
    model = PlantVersion
    label = "Plant"


def get_plant_version_repository(session: DatabaseSession) -> PlantVersionRepository:
    return PlantVersionRepository(session)
