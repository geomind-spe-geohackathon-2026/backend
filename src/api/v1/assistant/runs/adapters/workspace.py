import asyncio
import mimetypes
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge
from src.api.v1.assistant.runs.adapters.memory import DatabaseMemory
from src.api.v1.assistant.runs.adapters.rag import (
    read_knowledge_files,
    search_documents,
    search_knowledge,
)
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.rag_document import RagDocument
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.mcp_server import McpServerRepository
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.mcp_servers import server_of
from src.core.progress.project_state import project_state

DEFAULT_PLANT_NAME = "plant"
UNKNOWN_MEDIA_TYPE = "application/octet-stream"
MEMORY_ON = "on"


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


@dataclass(frozen=True, slots=True)
class Choices:
    """What a project chose for its runs: the shared memory, and its MCP servers."""

    memory_on: bool
    servers: tuple[dict[str, Any], ...]


async def read_choices(session: AsyncSession, project_id: UUID) -> Choices:
    project = await ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return Choices(False, ())
    ids = [UUID(item) for item in project.mcp or []]
    found = await McpServerRepository(session).by_ids(ids)
    servers = tuple(server_of(item) for item in found if item.enabled)
    return Choices(project.memory == MEMORY_ON, servers)


async def read_files(session: AsyncSession, project_id: UUID) -> list[RagDocument]:
    return await RagDocumentRepository(session).newest_by_name(project_id)


def to_media_type(name: str) -> str:
    return mimetypes.guess_type(name)[0] or UNKNOWN_MEDIA_TYPE


class DatabaseWorkspace:
    """geomind's ``Workspace`` on the backend's tables; every method blocks.

    ``plants`` holds the project's latest plant under the name in its document. ``case``
    returns the case as written with the bytes of every file it holds. geomind's loops
    read plants, file names, the case and the shared Knowledge on the event loop, where
    a blocking read would stall the loop it needs, so ``warm`` reads them ahead of the
    run and the loop gets that copy.
    """

    def __init__(
        self, bridge: LoopBridge, blobs: BlobStore, run_id: str | None = None
    ) -> None:
        self.bridge = bridge
        self.blobs = blobs
        self.run_id = run_id
        self.warmed: dict[str, tuple[dict[str, Any], list[RagDocument]]] = {}
        self.choices: dict[str, Choices] = {}
        self.states: dict[str, dict[str, Any]] = {}
        self.memories: dict[str, DatabaseMemory] = {}
        self.knowledge: list[RagDocument] | None = None
        self.cases: dict[str, tuple[dict[str, Any], dict[str, bytes]] | None] = {}

    async def warm(self, project_id: str) -> None:
        """Read a project's plants, files, case and the Knowledge ahead of a run."""
        plants = await asyncio.to_thread(
            self.bridge.call, read_plants, UUID(project_id)
        )
        rows = await asyncio.to_thread(self.bridge.call, read_files, UUID(project_id))
        self.warmed[project_id] = (plants, rows)
        self.knowledge = await asyncio.to_thread(self.bridge.call, read_knowledge_files)
        self.cases[project_id] = await asyncio.to_thread(self.read_case, project_id)
        choices = await asyncio.to_thread(
            self.bridge.call, read_choices, UUID(project_id)
        )
        self.choices[project_id] = choices
        self.states[project_id] = await asyncio.to_thread(
            self.bridge.call, project_state, UUID(project_id)
        )
        if choices.memory_on:
            memory = DatabaseMemory(self.bridge, project_id, self.run_id)
            await memory.warm()
            self.memories[project_id] = memory

    def project_state(self, project_id: str) -> dict[str, Any] | None:
        """Return where the project stands: its five steps and the versions behind them.

        geomind reads it for the next steps it suggests. Off the event loop it is read
        fresh, so a run's own changes count; on the loop the copy read before the run.
        """
        if self.bridge.in_loop():
            return self.states.get(project_id)
        state = self.bridge.call(project_state, UUID(project_id))
        self.states[project_id] = state
        return state

    def choices_of(self, project_id: str) -> Choices:
        if project_id not in self.choices:
            self.choices[project_id] = self.bridge.call(read_choices, UUID(project_id))
        return self.choices[project_id]

    def memory(self, project_id: str) -> DatabaseMemory | None:
        """Return the shared memory as the project sees it, or ``None`` when it is off.

        A project uses the memory only when it chose ``on``; one that has not chosen
        does not, so a competition run never reads it by chance.
        """
        if not self.choices_of(project_id).memory_on:
            return None
        if project_id not in self.memories:
            self.memories[project_id] = DatabaseMemory(
                self.bridge, project_id, self.run_id
            )
        return self.memories[project_id]

    def mcp(self, project_id: str) -> list[dict[str, Any]]:
        """Return the enabled MCP servers the project chose, each with its headers."""
        return list(self.choices_of(project_id).servers)

    def connectors(self, project_id: str) -> list[dict[str, Any]]:
        """``mcp`` under the name geomind used before its rename."""
        return self.mcp(project_id)

    def plants(self, project_id: str) -> dict[str, dict[str, Any]]:
        """Return ``{name: plant file dict}`` of the project, ``{}`` without a plant."""
        if self.bridge.in_loop() and project_id in self.warmed:
            return self.warmed[project_id][0]
        return self.bridge.call(read_plants, UUID(project_id))

    def case(
        self,
        project_id: str,
    ) -> tuple[dict[str, Any], dict[str, bytes]] | None:
        """Return the latest case as written and ``{name: bytes}``, or ``None``.

        Off the event loop it is read fresh, so a run's own changes count; on the loop
        the copy read last, before the run or since.
        """
        if self.bridge.in_loop() and project_id in self.cases:
            return self.cases[project_id]
        found = self.read_case(project_id)
        self.cases[project_id] = found
        return found

    def read_case(
        self,
        project_id: str,
    ) -> tuple[dict[str, Any], dict[str, bytes]] | None:
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

    def file_rows(self, project_id: str) -> list[RagDocument]:
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

    def knowledge_search(self, query: str) -> list[dict[str, Any]]:
        """Return passages of the shared Knowledge as ``[{id, document, title, page,
        text, score}]``, best first; ``document`` is what ``knowledge_file`` reads."""
        return self.bridge.call(search_knowledge, query)

    def knowledge_rows(self) -> list[RagDocument]:
        """Return the shared Knowledge documents; on the event loop the warmed copy."""
        if self.bridge.in_loop() and self.knowledge is not None:
            return self.knowledge
        return self.bridge.call(read_knowledge_files)

    def knowledge_files(self) -> list[dict[str, Any]]:
        """Return the shared Knowledge documents as ``[{name, size, media_type}]``."""
        rows = self.knowledge_rows()
        return [
            {"name": row.name, "size": row.size, "media_type": to_media_type(row.name)}
            for row in rows
        ]

    def knowledge_file(self, name: str) -> bytes | None:
        """Return the bytes of a shared Knowledge document, or ``None``."""
        rows = self.knowledge_rows()
        found = next((row for row in rows if row.name == name), None)
        return None if found is None else self.blobs.get_sync(found.object_key)

    def rag(self, project_id: str, query: str) -> list[dict[str, Any]]:
        """Return the project's matching documents as ``[{id, title, text, score}]``."""
        return self.bridge.call(search_documents, UUID(project_id), query)

    def documents(self, project_id: str, query: str) -> list[dict[str, Any]]:
        """``rag`` under the name geomind used before its rename."""
        return self.rag(project_id, query)
