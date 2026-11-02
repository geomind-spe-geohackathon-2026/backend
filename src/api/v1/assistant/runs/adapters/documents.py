from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.clients.postgres.repositories.document import DocumentRepository
from src.core.documents.search import search_documents as search

RESULT_LIMIT = 5


async def search_documents(
    session: AsyncSession,
    project_id: UUID,
    query: str,
) -> list[dict[str, Any]]:
    """Return ``[{id, title, text, score}]``, best first, for the assistant's search."""
    hits = await search(DocumentRepository(session), project_id, query, RESULT_LIMIT)
    return [{**hit, "id": str(hit["id"])} for hit in hits]
