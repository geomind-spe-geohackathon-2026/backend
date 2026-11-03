import asyncio
import mimetypes
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge
from src.api.v1.assistant.runs.adapters.documents import search_documents
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.document import Document
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.document import DocumentRepository
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)

DEFAULT_PLANT_NAME = "plant"
UNKNOWN_MEDIA_TYPE = "application/octet-stream"


async def read_plants(
    session: AsyncSession,
    project_id: UUID,
) -> dict[str, dict[str, Any]]:
    row = await PlantVersionRepository(session).latest_version(project_id)
    if row is None:
        return {}
    name = row.content.get("name")
    return {name if isinstance(name, str) and name else DEFAULT_PLANT_NAME: row.content}


async def read_case(
    session: AsyncSession,
    project_id: UUID,
) -> tuple[dict[str, Any], list[tuple[str, str]]] | None:
    version = await CaseVersionRepository(session).latest_version(project_id)
    if version is None:
        return None
    files = await CaseFileRepository(session).list_for_version(version.id)
    return version.content, [(file.name, file.object_key) for file in files]


async def read_files(session: AsyncSession, project_id: UUID) -> list[Document]:
    return await DocumentRepository(session).newest_by_name(project_id)


def to_media_type(name: str) -> str:
    return mimetypes.guess_type(name)[0] or UNKNOWN_MEDIA_TYPE


class DatabaseWorkspace:
    """geomind's ``Workspace`` on the backend's tables; every method blocks.

    ``plants`` holds the project's latest plant under the name in its document. ``case``
    returns the case as written with the bytes of every file it holds. geomind's loops
    read plants and file names on the event loop, where a blocking read would stall the
    loop it needs, so ``warm`` reads them ahead of the run and the loop gets that copy.
    """

    def __init__(self, bridge: LoopBridge, blobs: BlobStore) -> None:
        self.bridge = bridge
        self.blobs = blobs
        self.warmed: dict[str, tuple[dict[str, Any], list[Document]]] = {}

    async def warm(self, project_id: str) -> None:
        """Read a project's plants and uploaded files ahead of a run."""
        plants = await asyncio.to_thread(
            self.bridge.call, read_plants, UUID(project_id)
        )
        rows = await asyncio.to_thread(self.bridge.call, read_files, UUID(project_id))
        self.warmed[project_id] = (plants, rows)

    def plants(self, project_id: str) -> dict[str, dict[str, Any]]:
        """Return ``{name: plant file dict}`` of the project, ``{}`` without a plant."""
        if self.bridge.in_loop() and project_id in self.warmed:
            return self.warmed[project_id][0]
        return self.bridge.call(read_plants, UUID(project_id))

    def case(
        self,
        project_id: str,
    ) -> tuple[dict[str, Any], dict[str, bytes]] | None:
        """Return the latest case as written and ``{name: bytes}``, or ``None``."""
        found = self.bridge.call(read_case, UUID(project_id))
        if found is None:
            return None
        content, rows = found
        return content, {name: self.read(key) for name, key in rows}

    def read(self, key: str) -> bytes:
        data = self.blobs.get_sync(key)
        if data is None:
            raise FileNotFoundError(f"case file {key!r} is missing from storage")
        return data

    def file_rows(self, project_id: str) -> list[Document]:
        if self.bridge.in_loop() and project_id in self.warmed:
            return self.warmed[project_id][1]
        return self.bridge.call(read_files, UUID(project_id))

    def files(self, project_id: str) -> list[dict[str, Any]]:
        """Return the project's uploaded files as ``[{name, size, media_type}]``."""
        rows = self.file_rows(project_id)
        return [
            {"name": row.name, "size": row.size, "media_type": to_media_type(row.name)}
            for row in rows
        ]

    def file(self, project_id: str, name: str) -> bytes | None:
        """Return the bytes of an uploaded file, or ``None`` when it does not exist."""
        rows = self.file_rows(project_id)
        found = next((row for row in rows if row.name == name), None)
        return None if found is None else self.blobs.get_sync(found.object_key)

    def documents(self, project_id: str, query: str) -> list[dict[str, Any]]:
        """Return matching documents as ``[{id, title, text, score}]``, best first."""
        return self.bridge.call(search_documents, UUID(project_id), query)
