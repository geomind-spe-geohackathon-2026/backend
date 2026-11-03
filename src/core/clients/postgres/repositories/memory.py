from typing import Any
from uuid import UUID

from sqlalchemy import or_, select

from src.core.clients.postgres.models.memory_entry import MemoryEntry
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession


class MemoryRepository(BaseRepository):
    async def visible(self, section: str, project_id: UUID) -> list[MemoryEntry]:
        """Return what a project may see: shared entries and its own, oldest first."""
        statement = (
            select(MemoryEntry)
            .where(
                MemoryEntry.section == section,
                or_(
                    MemoryEntry.project_id.is_(None),
                    MemoryEntry.project_id == project_id,
                ),
            )
            .order_by(MemoryEntry.created, MemoryEntry.id)
        )
        return list(await self.session.scalars(statement))

    async def get(
        self, section: str, entry_id: str, project_id: UUID | None = None
    ) -> MemoryEntry | None:
        """Return a shared entry, or with ``project_id`` that project's own."""
        owner = (
            MemoryEntry.project_id.is_(None)
            if project_id is None
            else MemoryEntry.project_id == project_id
        )
        statement = select(MemoryEntry).where(
            MemoryEntry.section == section,
            MemoryEntry.entry_id == entry_id,
            owner,
        )
        return await self.session.scalar(statement)

    async def put(
        self,
        section: str,
        data: dict[str, Any],
        project_id: UUID | None,
        by: tuple[str, str | None],
    ) -> MemoryEntry:
        """Keep an entry; one of the same section and id is replaced, as in geomind."""
        entry_id = str(data["id"])
        row = await self.get(section, entry_id, project_id)
        if row is None:
            row = MemoryEntry(section=section, entry_id=entry_id)
            self.session.add(row)
        row.data = data
        row.project_id = project_id
        row.created_by_kind, row.created_by = by
        await self.session.commit()
        return row

    async def remove(self, row: MemoryEntry) -> None:
        await self.session.delete(row)
        await self.session.commit()


def get_memory_repository(session: DatabaseSession) -> MemoryRepository:
    return MemoryRepository(session)
