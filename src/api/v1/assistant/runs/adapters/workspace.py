from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge
from src.api.v1.assistant.runs.adapters.documents import search_documents
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)

DEFAULT_PLANT_NAME = "plant"


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


class DatabaseWorkspace:
    """geomind's ``Workspace`` on the backend's tables; every method blocks.

    ``plants`` holds the project's latest plant under the name in its document. ``case``
    returns the case as written with the bytes of every file it holds.
    """

    def __init__(self, bridge: LoopBridge, blobs: BlobStore) -> None:
        self.bridge = bridge
        self.blobs = blobs

    def plants(self, project_id: str) -> dict[str, dict[str, Any]]:
        """Return ``{name: plant file dict}`` of the project, ``{}`` without a plant."""
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

    def documents(self, project_id: str, query: str) -> list[dict[str, Any]]:
        """Return matching documents as ``[{id, title, text, score}]``, best first."""
        return self.bridge.call(search_documents, UUID(project_id), query)
