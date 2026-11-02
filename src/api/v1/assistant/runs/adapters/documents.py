from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


async def search_documents(
    session: AsyncSession,
    project_id: UUID,
    query: str,
) -> list[dict[str, Any]]:
    """Return ``[{id, title, text, score}]``, best first, for the assistant's search.

    The project's documents are searched by ``src/core/documents``, which workspace
    documents own; until that package exists nothing is found. This is the one place
    to wire it.
    """
    return []
