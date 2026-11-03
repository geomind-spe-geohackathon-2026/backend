from uuid import UUID

from sqlalchemy import delete, select

from src.core.clients.postgres.models.document import Document
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.pagination.page import PageRequest, paginate


class DocumentRepository(BaseRepository):
    async def create(
        self,
        project_id: UUID,
        name: str,
        size: int,
        object_key: str,
        author_id: UUID,
    ) -> Document:
        document = Document(
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

    async def get_by_id(self, document_id: UUID) -> Document | None:
        return await self.session.get(Document, document_id)

    async def list_page(self, project_id: UUID, page: PageRequest) -> list[Document]:
        statement = select(Document).where(Document.project_id == project_id)
        statement = paginate(statement, Document.created, Document.id, page)
        return list(await self.session.scalars(statement))

    async def set_text(self, document: Document, text: str | None) -> Document:
        """Store the extracted text; ``None`` marks the extraction as failed."""
        document.text = text
        document.searchable = "failed" if text is None else "ready"
        await self.session.commit()
        return document

    async def search(self, project_id: UUID, words: list[str]) -> list[Document]:
        """Return ready documents whose text holds every word, ignoring case."""
        statement = select(Document).where(
            Document.project_id == project_id,
            Document.searchable == "ready",
        )
        for word in words:
            statement = statement.where(Document.text.icontains(word, autoescape=True))
        return list(await self.session.scalars(statement.order_by(Document.created)))

    async def newest_by_name(self, project_id: UUID) -> list[Document]:
        """Return the project's documents, the newest of each name, by name."""
        statement = (
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created)
        )
        rows = await self.session.scalars(statement)
        newest = {row.name: row for row in rows}
        return [newest[name] for name in sorted(newest)]

    async def object_keys(self, project_id: UUID) -> list[str]:
        statement = select(Document.object_key).where(Document.project_id == project_id)
        return list(await self.session.scalars(statement))

    async def delete(self, document_id: UUID) -> None:
        await self.session.execute(delete(Document).where(Document.id == document_id))
        await self.session.commit()


def get_document_repository(session: DatabaseSession) -> DocumentRepository:
    return DocumentRepository(session)
