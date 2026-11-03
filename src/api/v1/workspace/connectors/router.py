from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from src.api.v1.workspace.connectors import schemas, services
from src.core.clients.postgres.repositories.connector import (
    ConnectorRepository,
    get_connector_repository,
)
from src.core.security.access import AdminUser, CurrentUser

router = APIRouter(prefix="/connectors", tags=["Connectors"])

ConnectorRepositoryDependency = Annotated[
    ConnectorRepository, Depends(get_connector_repository)
]


@router.get("", response_model=list[schemas.Connector])
async def list_connectors(
    _user: CurrentUser, repository: ConnectorRepositoryDependency
) -> list[schemas.Connector]:
    return await services.list_connectors(repository)


@router.post("", response_model=schemas.Connector, status_code=status.HTTP_201_CREATED)
async def create_connector(
    payload: schemas.ConnectorCreate,
    _admin: AdminUser,
    repository: ConnectorRepositoryDependency,
) -> schemas.Connector:
    return await services.create_connector(payload, repository)


@router.patch("/{connector_id}", response_model=schemas.Connector)
async def update_connector(
    connector_id: UUID,
    payload: schemas.ConnectorUpdate,
    _admin: AdminUser,
    repository: ConnectorRepositoryDependency,
) -> schemas.Connector:
    return await services.update_connector(connector_id, payload, repository)


@router.post("/{connector_id}/check", response_model=schemas.Connector)
async def check_connector(
    connector_id: UUID,
    _admin: AdminUser,
    repository: ConnectorRepositoryDependency,
) -> schemas.Connector:
    connector = await services.require_connector(connector_id, repository)
    return await services.check_connector(connector, repository)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: UUID,
    _admin: AdminUser,
    repository: ConnectorRepositoryDependency,
) -> None:
    await services.delete_connector(connector_id, repository)
