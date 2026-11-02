from typing import Any
from uuid import UUID

import geomind as gd
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.redis.models.run_delta import PendingDelta
from src.core.clients.redis.repositories.run_delta import RunDeltaRepository
from src.core.sse.events import StreamEvent
from src.core.sse.publish import publish_event_async

TERMINAL_STATUSES = ("done", "failed", "cancelled")
TEXT_DELTA = "text.delta"
STEP_FINISHED = "step.finished"


class EventPublisher(gd.callbacks.Callback):
    """Send the public events of a run to the browser through Redis.

    geomind saves an event before it tells the callbacks, so a stored event is already
    in the database when it is published. A ``text.delta`` is never stored; it is
    kept in a short-lived buffer for reconnects until its step finishes.
    """

    def __init__(self, redis: Redis, channel: str, run_id: UUID, ttl: int) -> None:
        self.redis = redis
        self.channel = channel
        self.run_id = str(run_id)
        self.ttl = ttl
        self.deltas = RunDeltaRepository(redis)

    async def on_event(self, engine: Any, event: Any) -> None:
        """Publish one event if it is public."""
        if not event.is_public:
            return
        if event.type == TEXT_DELTA:
            await self.buffer(event)
            sequence = None
        else:
            await self.forget(event)
            sequence = event.sequence
        stream_event = StreamEvent(event.type, event.data(), sequence)
        await publish_event_async(self.redis, self.channel, stream_event)

    async def buffer(self, event: Any) -> None:
        delta = PendingDelta(event.agent, event.parent, event.index, event.text)
        await self.deltas.append(self.run_id, delta, self.ttl)

    async def forget(self, event: Any) -> None:
        if event.type != STEP_FINISHED:
            return
        await self.deltas.clear(self.run_id, event.agent, event.parent, event.index)


async def set_values(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    values: dict[str, Any],
) -> None:
    async with factory() as session:
        run = await RunRepository(session).get_by_id(run_id)
        if run is not None:
            await RunRepository(session).update(run, values)


def usage_columns(event: Any) -> dict[str, Any]:
    return {
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "cost": event.cost,
    }


def finish_columns(event: Any) -> dict[str, Any]:
    values: dict[str, Any] = {"status": event.status, "request": None}
    if event.status in TERMINAL_STATUSES:
        values["ended"] = utc_now()
    if event.status == "failed":
        values["error"] = {"code": event.stop_reason, "message": event.message or ""}
    return values


class RunRecorder(gd.callbacks.Callback):
    """Keep the run's row current while the run goes.

    It is listed before the publisher, so a client that receives ``request`` or
    ``run.finished`` finds the row already in that state. It follows the root run for
    its loop, running totals and end; a request of any agent makes the run wait.
    """

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        run_id: UUID,
    ) -> None:
        self.factory = factory
        self.run_id = run_id

    async def on_event(self, engine: Any, event: Any) -> None:
        """Write the columns an event changes."""
        values = self.columns(event)
        if values:
            await set_values(self.factory, self.run_id, values)

    def columns(self, event: Any) -> dict[str, Any]:
        if event.type == "request":
            return {"status": "waiting", "request": event.data()}
        if event.parent is not None:
            return {}
        if event.type == "run.started" and event.loop is not None:
            return {"loop": event.loop}
        if event.type == "usage":
            return usage_columns(event)
        if event.type == "run.finished":
            return finish_columns(event)
        return {}
