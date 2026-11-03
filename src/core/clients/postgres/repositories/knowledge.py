from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, or_, select

from src.core.clients.postgres.models.knowledge_entry import KnowledgeEntry
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.pagination.page import PageRequest, paginate


class KnowledgeRepository(BaseRepository):
    async def list_page(
        self, section: str, words: list[str], page: PageRequest
    ) -> list[KnowledgeEntry]:
        """Return a section's entries whose text holds every word, ignoring case."""
        statement = select(KnowledgeEntry).where(KnowledgeEntry.section == section)
        for word in words:
            statement = statement.where(
                cast(KnowledgeEntry.data, String).icontains(word, autoescape=True)
            )
        statement = paginate(statement, KnowledgeEntry.created, KnowledgeEntry.id, page)
        return list(await self.session.scalars(statement))

    async def visible(self, section: str, project_id: UUID) -> list[KnowledgeEntry]:
        """Return what a project may see: shared entries and its own, oldest first."""
        statement = (
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.section == section,
                or_(
                    KnowledgeEntry.project_id.is_(None),
                    KnowledgeEntry.project_id == project_id,
                ),
            )
            .order_by(KnowledgeEntry.created, KnowledgeEntry.id)
        )
        return list(await self.session.scalars(statement))

    async def get(
        self, section: str, entry_id: str, project_id: UUID | None = None
    ) -> KnowledgeEntry | None:
        """Return a shared entry, or with ``project_id`` that project's own."""
        owner = (
            KnowledgeEntry.project_id.is_(None)
            if project_id is None
            else KnowledgeEntry.project_id == project_id
        )
        statement = select(KnowledgeEntry).where(
            KnowledgeEntry.section == section,
            KnowledgeEntry.entry_id == entry_id,
            owner,
        )
        return await self.session.scalar(statement)

    async def put(
        self,
        section: str,
        data: dict[str, Any],
        project_id: UUID | None,
        by: tuple[str, str | None],
    ) -> KnowledgeEntry:
        """Keep an entry; one of the same section and id is replaced, as in geomind."""
        entry_id = str(data["id"])
        row = await self.get(section, entry_id, project_id)
        if row is None:
            row = KnowledgeEntry(section=section, entry_id=entry_id)
            self.session.add(row)
        row.data = data
        row.project_id = project_id
        row.created_by_kind, row.created_by = by
        await self.session.commit()
        return row

    async def remove(self, row: KnowledgeEntry) -> None:
        await self.session.delete(row)
        await self.session.commit()


def get_knowledge_repository(session: DatabaseSession) -> KnowledgeRepository:
    return KnowledgeRepository(session)
