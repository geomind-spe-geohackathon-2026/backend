import csv
import io
import os
from typing import Any
from uuid import UUID

from src.api.v1.workspace.knowledge import schemas
from src.core.clients.postgres.models.knowledge_entry import KnowledgeEntry
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.knowledge import KnowledgeRepository
from src.core.errors import AppError, NotFoundError, ValidationFailedError
from src.core.geomind import memory
from src.core.pagination.page import Page, PageRequest, encode_cursor

SIMILARITY_SETTING = "GEOMIND_MEMORY_SIMILARITY"
CSV_ORIGIN = "upload"


class EntryNotFoundError(NotFoundError):
    code = "entry_not_found"


def to_entry(row: KnowledgeEntry) -> dict[str, Any]:
    return {
        **row.data,
        "id": row.entry_id,
        "section": row.section,
        "project": row.project_id,
        "created": row.created,
        "updated": row.updated,
        "created_by": {"kind": row.created_by_kind, "id": row.created_by},
    }


async def list_entries(
    section: str, query: str | None, page: PageRequest, repository: KnowledgeRepository
) -> Page:
    words = (query or "").split()
    rows = await repository.list_page(section, words, page)
    items = rows[: page.limit]
    last = items[-1] if len(rows) > page.limit else None
    return Page(
        items=[schemas.Entry.model_validate(to_entry(row)) for row in items],
        next=None if last is None else encode_cursor(last.created, last.id),
    )


async def require_entry(
    section: str,
    entry_id: str,
    project: UUID | None,
    repository: KnowledgeRepository,
) -> KnowledgeEntry:
    row = await repository.get(section, entry_id, project)
    if row is None:
        raise EntryNotFoundError("Entry not found")
    return row


async def get_entry(
    section: str, entry_id: str, project: UUID | None, repository: KnowledgeRepository
) -> dict[str, Any]:
    return to_entry(await require_entry(section, entry_id, project, repository))


def by_user(user: User) -> tuple[str, str]:
    return "user", str(user.id)


async def add_entry(
    payload: schemas.EntryInput, user: User, repository: KnowledgeRepository
) -> dict[str, Any]:
    """Add a knowledge entry a person wrote, checked as geomind checks its own."""
    fields = schemas.entry_fields(payload.model_dump())
    if await repository.get(memory.KNOWLEDGE, fields["id"], payload.project):
        raise ValidationFailedError({"id": "An entry with this id exists"})
    checked = memory.checked_entry({**fields, "origin": "user"})
    row = await repository.put(
        memory.KNOWLEDGE, checked, payload.project, by_user(user)
    )
    return to_entry(row)


async def change_entry(
    entry_id: str,
    project: UUID | None,
    payload: schemas.EntryChange,
    user: User,
    repository: KnowledgeRepository,
) -> dict[str, Any]:
    """Change fields of a knowledge entry; the whole entry is checked again."""
    row = await require_entry(memory.KNOWLEDGE, entry_id, project, repository)
    change = payload.model_dump()
    if "id" in change and change["id"] != entry_id:
        raise ValidationFailedError({"id": "The id of an entry cannot change"})
    merged = {**row.data, **change, "id": entry_id}
    fields = {key: value for key, value in merged.items() if value is not None}
    checked = memory.checked_entry(fields)
    saved = await repository.put(
        memory.KNOWLEDGE, checked, row.project_id, by_user(user)
    )
    return to_entry(saved)


async def delete_entry(
    section: str, entry_id: str, project: UUID | None, repository: KnowledgeRepository
) -> None:
    await repository.remove(await require_entry(section, entry_id, project, repository))


def rows_of(data: bytes) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValidationFailedError({"file": "The file is not UTF-8 text"}) from error
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValidationFailedError({"file": "The file has no header row"})
    return [dict(row) for row in reader]


async def import_entries(
    data: bytes, user: User, repository: KnowledgeRepository
) -> schemas.ImportReport:
    """Add the rows of a catalogue CSV; a row geomind refuses is reported, not added."""
    added = replaced = 0
    errors = []
    for number, row in enumerate(rows_of(data), start=2):
        try:
            entries = memory.catalogue_entries([row], CSV_ORIGIN)
        except AppError as error:
            if error.code == "not_implemented":
                raise
            errors.append(schemas.ImportProblem(row=number, message=str(error.details)))
            continue
        for entry in entries:
            known = await repository.get(memory.KNOWLEDGE, str(entry["id"]))
            await repository.put(memory.KNOWLEDGE, entry, None, by_user(user))
            replaced, added = (replaced + 1, added) if known else (replaced, added + 1)
    return schemas.ImportReport(added=added, replaced=replaced, errors=errors)


def read_settings() -> schemas.KnowledgeSettings:
    raw = os.environ.get(SIMILARITY_SETTING)
    try:
        similarity = float(raw) if raw else memory.similarity_threshold()
    except ValueError:
        similarity = None
    return schemas.KnowledgeSettings(
        sections=list(memory.SECTIONS),
        similarity=similarity,
        available=memory.is_available(),
    )
