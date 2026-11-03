from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.clients.postgres.models.rag_document import RagDocument
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.rag.search import search_documents as search
from src.core.rag.search import search_knowledge as search_shared

RESULT_LIMIT = 5
KNOWLEDGE_LIMIT = 8


async def search_documents(
    session: AsyncSession,
    project_id: UUID,
    query: str,
) -> list[dict[str, Any]]:
    """Return ``[{id, title, text, score}]``, best first, for the assistant's search."""
    hits = await search(RagDocumentRepository(session), project_id, query, RESULT_LIMIT)
    return [{**hit, "id": str(hit["id"])} for hit in hits]


async def search_knowledge(session: AsyncSession, query: str) -> list[dict[str, Any]]:
    """Return passages of the shared Knowledge, best first, each with its citation."""
    return list(
        await search_shared(RagDocumentRepository(session), query, KNOWLEDGE_LIMIT)
    )


async def read_knowledge_files(session: AsyncSession) -> list[RagDocument]:
    return await RagDocumentRepository(session).newest_by_name(None)
