import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge
from src.core.clients.postgres.repositories.memory import MemoryRepository

SECTIONS = ("experience",)


async def read_visible(
    session: AsyncSession, project_id: UUID
) -> dict[str, list[dict[str, Any]]]:
    repository = MemoryRepository(session)
    return {
        section: [row.data for row in await repository.visible(section, project_id)]
        for section in SECTIONS
    }


async def write_entry(
    session: AsyncSession,
    section: str,
    entry: dict[str, Any],
    project_id: UUID,
    run_id: str | None,
) -> None:
    await MemoryRepository(session).put(section, entry, None, ("agent", run_id))


class DatabaseMemory:
    """geomind's ``Memory`` for one project's runs: the agents' shared experience.

    Entries are kept as geomind gives them and never checked or edited here. They are
    read before the run, as geomind may read them on the event loop; what the run
    writes is added to that copy too.
    """

    def __init__(self, bridge: LoopBridge, project_id: str, run_id: str | None) -> None:
        self.bridge = bridge
        self.project_id = UUID(project_id)
        self.run_id = run_id
        self.warmed: dict[str, list[dict[str, Any]]] | None = None

    async def warm(self) -> None:
        self.warmed = await asyncio.to_thread(
            self.bridge.call, read_visible, self.project_id
        )

    def entries(self, section: str) -> list[dict[str, Any]]:
        """Return the entries of one section the project may see, oldest first."""
        if self.warmed is None or not self.bridge.in_loop():
            self.warmed = self.bridge.call(read_visible, self.project_id)
        return list(self.warmed.get(section, []))

    def add(self, section: str, entry: dict[str, Any]) -> None:
        """Keep one entry; one of the same section and id is replaced."""
        arguments = (section, dict(entry), self.project_id, self.run_id)
        if self.bridge.in_loop():
            self.bridge.loop.create_task(self.bridge.run(write_entry, arguments))
        else:
            self.bridge.call(write_entry, *arguments)
        if self.warmed is not None:
            kept = [
                item
                for item in self.warmed.get(section, [])
                if item.get("id") != entry.get("id")
            ]
            self.warmed[section] = [*kept, dict(entry)]
