from collections.abc import AsyncIterator, Awaitable, Callable, Collection
from typing import Annotated

from fastapi.sse import ServerSentEvent
from redis.asyncio import Redis

from fastapi import Header
from src.core.errors import ValidationFailedError
from src.core.settings import settings
from src.core.sse.events import StreamEvent, decode_event

HEARTBEAT_COMMENT = "heartbeat"
NO_EVENT = -1

Replay = Callable[[int], Awaitable[list[StreamEvent]]]


def last_event_id(
    last_event_id: Annotated[str | None, Header()] = None,
) -> int:
    """Return the sequence a client has seen, or ``NO_EVENT`` for a new stream."""
    if last_event_id is None:
        return NO_EVENT
    try:
        return int(last_event_id)
    except ValueError as error:
        raise ValidationFailedError(
            {"last-event-id": "Last-Event-ID must be an integer"}
        ) from error


def to_sse(event: StreamEvent) -> ServerSentEvent:
    identifier = None if event.sequence is None else str(event.sequence)
    return ServerSentEvent(event=event.type, data=event.data, id=identifier)


def advance(last: int, event: StreamEvent) -> int:
    return last if event.sequence is None else max(last, event.sequence)


async def follow(
    redis: Redis,
    channel: str,
    replay: Replay,
    after: int,
    final_types: Collection[str],
    heartbeat_seconds: float | None = None,
) -> AsyncIterator[ServerSentEvent]:
    """Stream a job's events to a client.

    It subscribes to ``channel`` first, so nothing published afterwards is lost; then it
    yields the stored events ``replay(after)`` returns, then the live events, skipping
    any whose sequence it has already sent. A comment is sent whenever nothing arrives
    for ``heartbeat_seconds``, so proxies keep the connection open. The stream ends
    after an event whose type is in ``final_types``; the subscription is always closed.
    """
    interval = heartbeat_seconds or settings.SSE_HEARTBEAT_SECONDS
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        last = after
        for event in await replay(after):
            last = advance(last, event)
            yield to_sse(event)
            if event.type in final_types:
                return
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=interval,
            )
            if message is None:
                yield ServerSentEvent(comment=HEARTBEAT_COMMENT)
                continue
            event = decode_event(message["data"])
            if event.sequence is not None and event.sequence <= last:
                continue
            last = advance(last, event)
            yield to_sse(event)
            if event.type in final_types:
                return
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
