from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.core.clients.postgres.models.connector import Connector
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession


class ConnectorRepository(BaseRepository):
    async def list_all(self) -> list[Connector]:
        statement = select(Connector).order_by(Connector.name)
        return list(await self.session.scalars(statement))

    async def get_by_id(self, connector_id: UUID) -> Connector | None:
        return await self.session.get(Connector, connector_id)

    async def get_by_name(self, name: str) -> Connector | None:
        return await self.session.scalar(
            select(Connector).where(Connector.name == name)
        )

    async def by_ids(self, ids: list[UUID]) -> list[Connector]:
        if not ids:
            return []
        statement = (
            select(Connector).where(Connector.id.in_(ids)).order_by(Connector.name)
        )
        return list(await self.session.scalars(statement))

    async def create(self, values: dict[str, Any]) -> Connector:
        connector = Connector(**values)
        self.session.add(connector)
        await self.session.commit()
        return connector

    async def update(self, connector: Connector, values: dict[str, Any]) -> Connector:
        for key, value in values.items():
            setattr(connector, key, value)
        await self.session.commit()
        return connector

    async def delete(self, connector: Connector) -> None:
        await self.session.delete(connector)
        await self.session.commit()


def get_connector_repository(session: DatabaseSession) -> ConnectorRepository:
    return ConnectorRepository(session)
