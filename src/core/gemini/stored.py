"""Case files read back from the object store, by the rows that name them."""

import asyncio
from uuid import UUID

import gemini as gm

from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.case_file import CaseFile
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.gemini import case
from src.core.gemini.errors import CaseFileNotFoundError


async def stored_files(rows: list[CaseFile], blobs: BlobStore) -> dict[str, bytes]:
    """Read the bytes of every file a case version holds; none touches the store."""
    files = {}
    for row in rows:
        data = await blobs.get(row.object_key)
        if data is None:
            raise CaseFileNotFoundError(f"File {row.name} is missing from storage")
        files[row.name] = data
    return files


async def latest_case(
    project_id: UUID,
    cases: CaseVersionRepository,
    files: CaseFileRepository,
    blobs: BlobStore,
) -> gm.Case | None:
    """Return the latest case built with its files; None if absent or incomplete."""
    latest = await cases.latest_version(project_id)
    if latest is None:
        return None
    stored = await stored_files(await files.list_for_version(latest.id), blobs)
    return await asyncio.to_thread(case.build, latest.content, stored)
