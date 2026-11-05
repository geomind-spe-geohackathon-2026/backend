"""What every versioned document shares: base check, latest version, authors."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from src.core.clients.postgres.repositories.user import UserRepository
from src.core.clients.postgres.repositories.version import VersionRepository
from src.core.errors import AppError, ConflictError


class Author(BaseModel):
    id: UUID
    name: str


ASSISTANT_NOTE = "by the assistant"
"""What every note of a version the assistant saved holds (QA-110)."""


class Version(BaseModel):
    number: int
    note: str
    author: Author
    created: datetime
    by: str


def saved_by(note: str) -> str:
    """Return ``assistant`` for a version the assistant saved, else ``user``."""
    return "assistant" if ASSISTANT_NOTE in note else "user"


def check_base(latest: Any | None, base: int | None) -> None:
    """Raise conflict with the latest number unless ``base`` is the latest version."""
    number = latest.number if latest else None
    if base != number:
        raise ConflictError(
            "Another version was saved since this one was read",
            details={"latest": number},
        )


async def latest_version(
    repository: VersionRepository,
    project_id: UUID,
    missing: type[AppError],
) -> Any:
    """Return the latest version of a project's document, or raise ``missing``."""
    latest = await repository.latest_version(project_id)
    if latest is None:
        raise missing("Nothing is saved yet")
    return latest


async def describe_versions(
    rows: list[Any],
    users: UserRepository,
) -> list[Version]:
    """Return the contract's version objects for rows, with the authors' names."""
    names: dict[UUID, str] = {}
    for row in rows:
        if row.author_id not in names:
            author = await users.get_by_id(row.author_id)
            names[row.author_id] = author.name if author else ""
    return [
        Version(
            number=row.number,
            note=row.note,
            author=Author(id=row.author_id, name=names[row.author_id]),
            created=row.created,
            by=saved_by(row.note),
        )
        for row in rows
    ]
