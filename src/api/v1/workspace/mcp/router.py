from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from src.api.v1.workspace.mcp import schemas, services
from src.core.clients.postgres.repositories.mcp_server import (
    McpServerRepository,
    get_mcp_server_repository,
)
from src.core.security.access import AdminUser, CurrentUser

router = APIRouter(prefix="/mcp", tags=["MCP"])

McpServerRepositoryDependency = Annotated[
    McpServerRepository, Depends(get_mcp_server_repository)
]


@router.get("", response_model=list[schemas.McpServer])
async def list_servers(
    _user: CurrentUser, repository: McpServerRepositoryDependency
) -> list[schemas.McpServer]:
    return await services.list_servers(repository)


@router.post("", response_model=schemas.McpServer, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: schemas.McpServerCreate,
    _admin: AdminUser,
    repository: McpServerRepositoryDependency,
) -> schemas.McpServer:
    return await services.create_server(payload, repository)


@router.patch("/{server_id}", response_model=schemas.McpServer)
async def update_server(
    server_id: UUID,
    payload: schemas.McpServerUpdate,
    _admin: AdminUser,
    repository: McpServerRepositoryDependency,
) -> schemas.McpServer:
    return await services.update_server(server_id, payload, repository)


@router.post("/{server_id}/check", response_model=schemas.McpServer)
async def check_server(
    server_id: UUID,
    _admin: AdminUser,
    repository: McpServerRepositoryDependency,
) -> schemas.McpServer:
    server = await services.require_server(server_id, repository)
    return await services.check_server(server, repository)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: UUID,
    _admin: AdminUser,
    repository: McpServerRepositoryDependency,
) -> None:
    await services.delete_server(server_id, repository)
