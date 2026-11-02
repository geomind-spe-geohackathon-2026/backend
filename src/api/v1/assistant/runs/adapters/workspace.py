from pathlib import Path
from typing import Any
from uuid import UUID

from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge
from src.api.v1.assistant.runs.adapters.documents import search_documents
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.gemini import plant as gemini_plant
from src.core.settings import settings


class WorkspaceFileError(ValueError):
    """A case file name that is not a bare file name."""


async def read_plant(session: AsyncSession, project_id: UUID) -> dict[str, Any] | None:
    row = await PlantVersionRepository(session).latest_version(project_id)
    return None if row is None else row.content


async def read_case(
    session: AsyncSession,
    project_id: UUID,
) -> tuple[dict[str, Any], list[tuple[str, str]]] | None:
    version = await CaseVersionRepository(session).latest_version(project_id)
    if version is None:
        return None
    files = await CaseFileRepository(session).list_for_version(version.id)
    return version.content, [(file.name, file.object_key) for file in files]


def write_case_files(
    minio: Minio,
    files: list[tuple[str, str]],
    folder: Path,
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, object_key in files:
        if Path(name).name != name:
            raise WorkspaceFileError(f"case file {name!r} is not a bare file name")
        response = minio.get_object(settings.MINIO_BUCKET_NAME, object_key)
        try:
            (folder / name).write_bytes(response.read())
        finally:
            response.close()
            response.release_conn()


class DatabaseWorkspace:
    """geomind's ``Workspace`` on the backend's tables; every method blocks.

    The files of a case are copied from MinIO into a folder of this run, which the
    caller removes when the run ends.
    """

    def __init__(self, bridge: LoopBridge, minio: Minio, folder: Path) -> None:
        self.bridge = bridge
        self.minio = minio
        self.folder = folder

    def plant(self, project_id: str) -> Any:
        """Return the project's latest plant as a gemini plant, or ``None``."""
        content = self.bridge.call(read_plant, UUID(project_id))
        return None if content is None else gemini_plant.from_dict(content)

    def case(self, project_id: str) -> tuple[dict[str, Any], Path] | None:
        """Return the latest case as written and the folder holding its files."""
        found = self.bridge.call(read_case, UUID(project_id))
        if found is None:
            return None
        content, files = found
        folder = self.folder / project_id
        write_case_files(self.minio, files, folder)
        return content, folder

    def documents(self, project_id: str, query: str) -> list[dict[str, Any]]:
        """Return matching documents as ``[{id, title, text, score}]``, best first."""
        return self.bridge.call(search_documents, UUID(project_id), query)
