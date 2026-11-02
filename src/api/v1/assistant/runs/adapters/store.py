import asyncio
from typing import Any
from uuid import UUID

import geomind as gd
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge
from src.core.clients.postgres.repositories.chat_state import ChatStateRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.run_artifact import (
    RunArtifactRepository,
)
from src.core.clients.postgres.repositories.run_event import RunEventRepository


async def add_event(
    session: AsyncSession,
    run_id: UUID,
    sequence: int,
    event_type: str,
    public: bool,
    data: dict[str, Any],
) -> None:
    await RunEventRepository(session).add(run_id, sequence, event_type, public, data)


async def read_events(session: AsyncSession, run_id: UUID) -> list[dict[str, Any]]:
    rows = await RunEventRepository(session).after(run_id, -1)
    return [dict(row.data) for row in rows]


async def read_history(
    session: AsyncSession,
    chat_id: UUID,
    run_id: UUID,
) -> list[tuple[str, str]]:
    rows = await MessageRepository(session).history(chat_id)
    return [(row.role, row.content) for row in rows if row.run_id != run_id]


async def write_state(
    session: AsyncSession,
    chat_id: UUID,
    state: dict[str, Any],
) -> None:
    await ChatStateRepository(session).save(chat_id, state)


async def read_state(session: AsyncSession, chat_id: UUID) -> dict[str, Any] | None:
    row = await ChatStateRepository(session).latest(chat_id)
    return None if row is None else row.state


async def write_artifact(
    session: AsyncSession,
    run_id: UUID | None,
    chat_id: UUID,
    key: str,
    data: Any,
) -> None:
    await RunArtifactRepository(session).save(run_id, chat_id, key, data)


async def read_run_artifact(session: AsyncSession, run_id: UUID, key: str) -> Any:
    row = await RunArtifactRepository(session).newest_for_run(run_id, key)
    return None if row is None else row.data


async def read_chat_artifact(session: AsyncSession, chat_id: UUID, key: str) -> Any:
    row = await RunArtifactRepository(session).newest_for_chat(chat_id, key)
    return None if row is None else row.data


class DatabaseRunStore:
    """geomind's ``RunStore`` on the backend's tables.

    One store serves one run of one chat: a run's artifacts carry both ids and are read by
    ``(run, key)``; a chat's artifacts have no run and are read by ``(chat, key)``, so the
    chat's next message reads what the first saved there. The two spaces are separate. A message of the run itself is left out of the history, because
    geomind adds it. Every method blocks and must be called from a thread.
    """

    def __init__(self, bridge: LoopBridge, run_id: UUID, chat_id: UUID) -> None:
        self.bridge = bridge
        self.run_id = run_id
        self.chat_id = chat_id
        self.warmed: list[Any] | None = None

    async def warm(self, run_id: str) -> None:
        """Read a run's events ahead of ``resume``, which reads them on the loop."""
        self.warmed = await asyncio.to_thread(self.load_events, run_id)

    def save_event(self, run_id: str, event: Any) -> None:
        """Store the full ``event.to_dict()``, public or internal."""
        self.bridge.call(
            add_event,
            UUID(run_id),
            event.sequence,
            event.type,
            event.is_public,
            event.to_dict(),
        )

    def load_events(self, run_id: str) -> list[Any]:
        """Return the run's events in sequence order, rebuilt by geomind."""
        if self.warmed is not None and self.bridge.in_loop():
            return self.warmed
        rows = self.bridge.call(read_events, UUID(run_id))
        return [gd.event_from_dict(row) for row in rows]

    def load_history(self, chat_id: str) -> list[Any]:
        """Return the chat's user and assistant messages, oldest first."""
        rows = self.bridge.call(read_history, UUID(chat_id), self.run_id)
        return [gd.Message(role=role, content=content) for role, content in rows]

    def save_state(self, chat_id: str, state: dict[str, Any]) -> None:
        """Store the problem state as given, as the next version."""
        self.bridge.call(write_state, UUID(chat_id), state)

    def load_state(self, chat_id: str) -> dict[str, Any] | None:
        """Return the newest problem state, or ``None``."""
        return self.bridge.call(read_state, UUID(chat_id))

    def save_artifact(self, run_id: str, key: str, data: Any) -> None:
        """Save bytes or a JSON value of a run."""
        self.bridge.call(write_artifact, UUID(run_id), self.chat_id, key, data)

    def load_artifact(self, run_id: str, key: str) -> Any:
        """Return the newest artifact of a run under a key, or ``None``."""
        return self.bridge.call(read_run_artifact, UUID(run_id), key)

    def save_chat_artifact(self, chat_id: str, key: str, data: Any) -> None:
        """Save bytes or a JSON value in the chat's own space, apart from every run's."""
        self.bridge.call(write_artifact, None, UUID(chat_id), key, data)

    def load_chat_artifact(self, chat_id: str, key: str) -> Any:
        """Return the newest artifact of the chat under a key, or ``None``."""
        return self.bridge.call(read_chat_artifact, UUID(chat_id), key)
