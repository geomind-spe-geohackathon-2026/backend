from typing import TypedDict
from uuid import UUID

from src.core.clients.postgres.repositories.document import DocumentRepository

SNIPPET_CHARACTERS = 300


class DocumentHit(TypedDict):
    id: UUID
    title: str
    text: str
    score: int


def snippet_of(text: str, word: str) -> str:
    """Return the text around the first place the word occurs."""
    start = max(text.lower().find(word) - SNIPPET_CHARACTERS // 2, 0)
    return text[start : start + SNIPPET_CHARACTERS]


async def search_documents(
    repository: DocumentRepository,
    project_id: UUID,
    query: str,
    limit: int,
) -> list[DocumentHit]:
    """Find ready documents of a project that hold every word of the query.

    The score is the number of times the words occur; the best come first.
    """
    words = query.lower().split()
    if not words:
        return []
    hits = [
        DocumentHit(
            id=document.id,
            title=document.name,
            text=snippet_of(document.text, words[0]),
            score=sum(document.text.lower().count(word) for word in words),
        )
        for document in await repository.search(project_id, words)
    ]
    return sorted(hits, key=lambda hit: hit["score"], reverse=True)[:limit]
