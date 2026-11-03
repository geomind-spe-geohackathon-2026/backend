from typing import TypedDict
from uuid import UUID

from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.rag.chunks import chunks_of

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
    repository: RagDocumentRepository,
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


class KnowledgeHit(TypedDict):
    id: str
    document: str
    title: str
    page: int | None
    text: str
    score: int


async def search_knowledge(
    repository: RagDocumentRepository, query: str, limit: int
) -> list[KnowledgeHit]:
    """Find the passages of the shared Knowledge that hold the query's words.

    A passage scores the times its words occur, more for one that holds every word;
    each keeps its document and page, so an agent can cite it.
    """
    words = query.lower().split()
    if not words:
        return []
    hits = []
    for document in await repository.search_any(None, words):
        for index, chunk in enumerate(chunks_of(document.text or "")):
            lowered = chunk.text.lower()
            counts = [lowered.count(word) for word in words]
            if not any(counts):
                continue
            whole = len(words) if all(counts) else 0
            hits.append(
                KnowledgeHit(
                    id=f"{document.id}#{index}",
                    document=document.name,
                    title=document.name,
                    page=chunk.page,
                    text=chunk.text,
                    score=sum(counts) + whole,
                )
            )
    return sorted(hits, key=lambda hit: hit["score"], reverse=True)[:limit]
