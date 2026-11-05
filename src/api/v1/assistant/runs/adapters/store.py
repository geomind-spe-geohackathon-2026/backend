import asyncio
import logging
from collections import OrderedDict
from typing import Any
from uuid import UUID

import geomind as gd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge
from src.api.v1.assistant.runs.adapters.replay import known_events
from src.core.clients.postgres.repositories.chat_state import ChatStateRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.run import RunRepository
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


logger = logging.getLogger(__name__)
RENUMBERED_KEPT = 512
"""The renumbered events a store remembers for its callbacks, the newest."""


async def read_last_sequence(session: AsyncSession, run_id: UUID) -> int:
    """Return the highest stored sequence of a run, 0 for none."""
    from src.core.clients.postgres.models.run_event import RunEvent

    statement = select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run_id)
    return await session.scalar(statement) or 0


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


async def read_chat_artifacts(session: AsyncSession, chat_id: UUID) -> dict[str, Any]:
    return await RunArtifactRepository(session).all_for_chat(chat_id)


async def read_chat_artifact(session: AsyncSession, chat_id: UUID, key: str) -> Any:
    row = await RunArtifactRepository(session).newest_for_chat(chat_id, key)
    return None if row is None else row.data


async def read_spent(
    session: AsyncSession, project_id: UUID, run_id: UUID | None
) -> gd.types.Usage:
    row = await RunRepository(session).usage_of_others(project_id, run_id)
    return gd.types.Usage(input_tokens=row[0], output_tokens=row[1], cost=row[2])


class DatabaseUsageLedger:
    """geomind's ``UsageLedger`` on the runs table.

    geomind's hook asks from the event loop, so the sum is read ahead of the run. It
    counts every other run of the project, a waiting one too, so pausing a chat does
    not take its spending out of the budget; the run itself geomind counts.
    """

    def __init__(self, bridge: LoopBridge, run_id: UUID | None = None) -> None:
        self.bridge = bridge
        self.run_id = run_id
        self.warmed: gd.types.Usage | None = None

    async def warm(self, project_id: str) -> None:
        """Read what the project spent ahead of a run."""
        self.warmed = await asyncio.to_thread(self.spent, project_id)

    def spent(self, project_id: str) -> gd.types.Usage:
        """Return the tokens and cost of the project's runs other than this one."""
        if self.bridge.in_loop() and self.warmed is not None:
            return self.warmed
        return self.bridge.call(read_spent, UUID(project_id), self.run_id)


class DatabaseRunStore:
    """geomind's ``RunStore`` on the backend's tables.

    One store serves one run of one chat. A run's artifacts carry both ids and are
    read by ``(run, key)``. A chat's artifacts have no run and are read by
    ``(chat, key)``, so the chat's next message reads what the first saved there; the
    two spaces are separate. A message of the run itself is left out of the history,
    because geomind adds it. Every method blocks and must be called from a thread.
    """

    def __init__(self, bridge: LoopBridge, run_id: UUID, chat_id: UUID) -> None:
        self.bridge = bridge
        self.run_id = run_id
        self.chat_id = chat_id
        self.warmed: dict[str, list[Any]] = {}
        self.warmed_artifacts: dict[str, Any] = {}
        self.last: dict[str, int] = {}
        self.renumbered: OrderedDict[int, int] = OrderedDict()

    async def warm(self, run_id: str) -> None:
        """Read a run's events ahead of the run, which reads them on the loop.

        The events this store saves afterwards join that copy, so the loop reads every
        event of the run.
        """
        self.warmed[run_id] = list(await asyncio.to_thread(self.load_events, run_id))
        self.last[run_id] = max(
            (event.sequence for event in self.warmed[run_id]), default=0
        )

    async def warm_chat(self, chat_id: str) -> None:
        """Read a chat's artifacts ahead of the run: geomind's async tools read them.

        ``save_profile`` and the like read case files from the event loop, where a
        blocking call would stall the loop it needs.
        """
        self.warmed_artifacts = await asyncio.to_thread(
            self.bridge.call, read_chat_artifacts, UUID(chat_id)
        )

    def save_event(self, run_id: str, event: Any) -> None:
        """Store the full ``event.to_dict()``, public or internal, in a rising sequence.

        A run resumed after a restart numbered its new events from below the stored ones
        (QA-336: request-797 was stored after event 943), so the stream and every reader that
        goes by sequence put the question in the past and the chat never showed its card. An
        event that would not come after the stored ones is stored as the next sequence; the
        callbacks read that number with ``stored_sequence``.
        """
        sequence = self.next_sequence(run_id, event)
        data = event.to_dict()
        if sequence != event.sequence:
            logger.warning(
                "Run %s: event %s numbered %s after %s; stored as %s",
                run_id, event.type, event.sequence, sequence - 1, sequence,
            )
            data["sequence"] = sequence
            self.renumbered[id(event)] = sequence
            while len(self.renumbered) > RENUMBERED_KEPT:
                self.renumbered.popitem(last=False)
            event = event.model_copy(update={"sequence": sequence})
        self.bridge.call(
            add_event,
            UUID(run_id),
            sequence,
            event.type,
            event.is_public,
            data,
        )
        if run_id in self.warmed:
            self.warmed[run_id].append(event)

    def next_sequence(self, run_id: str, event: Any) -> int:
        """Return the sequence to store an event under: its own, unless that is not new."""
        last = self.last.get(run_id)
        if last is None:
            last = self.bridge.call(read_last_sequence, UUID(run_id))
        sequence = max(event.sequence, last + 1)
        self.last[run_id] = sequence
        return sequence

    def stored_sequence(self, event: Any) -> int:
        """Return the sequence an event was stored under (QA-336)."""
        return self.renumbered.get(id(event), event.sequence)

    def load_events(self, run_id: str) -> list[Any]:
        """Return the run's events in sequence order, rebuilt by geomind."""
        if run_id in self.warmed and self.bridge.in_loop():
            return list(self.warmed[run_id])
        rows = self.bridge.call(read_events, UUID(run_id))
        return known_events(rows)

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
        """Save bytes or a JSON value in the chat's own space."""
        self.bridge.call(write_artifact, None, UUID(chat_id), key, data)
        self.warmed_artifacts[key] = data

    def load_chat_artifact(self, chat_id: str, key: str) -> Any:
        """Return the newest artifact of the chat under a key, or ``None``."""
        if self.bridge.in_loop():
            return self.warmed_artifacts.get(key)
        return self.bridge.call(read_chat_artifact, UUID(chat_id), key)
