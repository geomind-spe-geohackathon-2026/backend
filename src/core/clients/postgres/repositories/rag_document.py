from uuid import UUID

from sqlalchemy import delete, or_, select

from src.core.clients.postgres.models.rag_document import RagDocument
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.pagination.page import PageRequest, paginate

Doc = RagDocument


class RagDocumentRepository(BaseRepository):
    async def create(
        self,
        project_id: UUID | None,
        name: str,
        size: int,
        object_key: str,
        author_id: UUID,
    ) -> RagDocument:
        document = RagDocument(
            project_id=project_id,
            name=name,
            size=size,
            object_key=object_key,
            searchable="pending",
            author_id=author_id,
        )
        self.session.add(document)
        await self.session.commit()
        return document

    async def get_by_id(self, document_id: UUID) -> RagDocument | None:
        return await self.session.get(Doc, document_id)

    async def list_page(
        self, project_id: UUID | None, page: PageRequest
    ) -> list[RagDocument]:
        """Return a project's documents, or with ``None`` the shared Knowledge."""
        owner = (
            Doc.project_id.is_(None)
            if project_id is None
            else Doc.project_id == project_id
        )
        statement = select(Doc).where(owner)
        statement = paginate(statement, Doc.created, Doc.id, page)
        return list(await self.session.scalars(statement))

    async def set_text(self, document: RagDocument, text: str | None) -> RagDocument:
        """Store the extracted text; ``None`` marks the extraction as failed."""
        document.text = text
        document.searchable = "failed" if text is None else "ready"
        await self.session.commit()
        return document

    async def search(
        self, project_id: UUID | None, words: list[str]
    ) -> list[RagDocument]:
        """Return a project's ready documents holding every word, or the shared ones."""
        owner = (
            Doc.project_id.is_(None)
            if project_id is None
            else Doc.project_id == project_id
        )
        statement = select(Doc).where(owner, Doc.searchable == "ready")
        for word in words:
            statement = statement.where(Doc.text.icontains(word, autoescape=True))
        return list(await self.session.scalars(statement.order_by(Doc.created)))

    async def search_any(
        self, project_id: UUID | None, words: list[str]
    ) -> list[RagDocument]:
        """Return a project's ready documents, or the shared ones, holding any word."""
        owner = (
            Doc.project_id.is_(None)
            if project_id is None
            else Doc.project_id == project_id
        )
        found = or_(*(Doc.text.icontains(word, autoescape=True) for word in words))
        statement = select(Doc).where(owner, Doc.searchable == "ready", found)
        return list(await self.session.scalars(statement.order_by(Doc.created)))

    async def newest_by_name(self, project_id: UUID | None) -> list[RagDocument]:
        """Return a project's documents or the shared ones, the newest of each name."""
        owner = (
            Doc.project_id.is_(None)
            if project_id is None
            else Doc.project_id == project_id
        )
        statement = select(Doc).where(owner).order_by(Doc.created)
        rows = await self.session.scalars(statement)
        newest = {row.name: row for row in rows}
        return [newest[name] for name in sorted(newest)]

    async def object_keys(self, project_id: UUID) -> list[str]:
        statement = select(Doc.object_key).where(Doc.project_id == project_id)
        return list(await self.session.scalars(statement))

    async def delete(self, document_id: UUID) -> None:
        await self.session.execute(delete(Doc).where(Doc.id == document_id))
        await self.session.commit()


def get_rag_document_repository(session: DatabaseSession) -> RagDocumentRepository:
    return RagDocumentRepository(session)
