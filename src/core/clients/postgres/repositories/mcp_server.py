from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.core.clients.postgres.models.mcp_server import McpServer
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession


class McpServerRepository(BaseRepository):
    async def list_all(self) -> list[McpServer]:
        statement = select(McpServer).order_by(McpServer.name)
        return list(await self.session.scalars(statement))

    async def get_by_id(self, server_id: UUID) -> McpServer | None:
        return await self.session.get(McpServer, server_id)

    async def get_by_name(self, name: str) -> McpServer | None:
        return await self.session.scalar(
            select(McpServer).where(McpServer.name == name)
        )

    async def by_ids(self, ids: list[UUID]) -> list[McpServer]:
        if not ids:
            return []
        statement = (
            select(McpServer).where(McpServer.id.in_(ids)).order_by(McpServer.name)
        )
        return list(await self.session.scalars(statement))

    async def create(self, values: dict[str, Any]) -> McpServer:
        server = McpServer(**values)
        self.session.add(server)
        await self.session.commit()
        return server

    async def update(self, server: McpServer, values: dict[str, Any]) -> McpServer:
        for key, value in values.items():
            setattr(server, key, value)
        await self.session.commit()
        return server

    async def delete(self, server: McpServer) -> None:
        await self.session.delete(server)
        await self.session.commit()


def get_mcp_server_repository(session: DatabaseSession) -> McpServerRepository:
    return McpServerRepository(session)
