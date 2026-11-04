from collections.abc import AsyncIterator, Awaitable, Callable, Collection
from contextlib import aclosing
from typing import Annotated

from fastapi.sse import ServerSentEvent
from redis.asyncio import Redis

from fastapi import Header
from src.core.settings import settings
from src.core.sse.events import StreamEvent, decode_event

HEARTBEAT_COMMENT = "heartbeat"
NO_EVENT = -1

Replay = Callable[[int], Awaitable[list[StreamEvent]]]


def last_event_id(
    last_event_id: Annotated[str | None, Header()] = None,
) -> int:
    """Return the sequence a client has seen, or ``NO_EVENT`` for a new stream.

    An empty or non-numeric id (a reconnect after an event without an id) is a new stream, not
    a 422: the 422 stopped the chat's live stream for good (QA-044).
    """
    try:
        return int(last_event_id) if last_event_id else NO_EVENT
    except ValueError:
        return NO_EVENT


def to_sse(event: StreamEvent) -> ServerSentEvent:
    identifier = None if event.sequence is None else str(event.sequence)
    return ServerSentEvent(event=event.type, data=event.data, id=identifier)


def advance(last: int, event: StreamEvent) -> int:
    return last if event.sequence is None else max(last, event.sequence)


async def follow_events(
    redis: Redis,
    channel: str,
    replay: Replay,
    after: int,
    final_types: Collection[str],
    heartbeat_seconds: float | None = None,
) -> AsyncIterator[StreamEvent | None]:
    """Yield a job's events, whatever carries them to the client.

    It subscribes to ``channel`` first, so nothing published afterwards is lost; then it
    yields the stored events ``replay(after)`` returns, then the live events, skipping
    any whose sequence it has already sent. ``None`` is yielded whenever nothing arrives
    for ``heartbeat_seconds``, so a transport can keep its connection open. It ends
    after an event whose type is in ``final_types``; the subscription is always closed.
    """
    interval = heartbeat_seconds or settings.SSE_HEARTBEAT_SECONDS
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        last = after
        for event in await replay(after):
            last = advance(last, event)
            yield event
            if event.type in final_types:
                return
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=interval,
            )
            if message is None:
                yield None
                continue
            event = decode_event(message["data"])
            if event.sequence is not None and event.sequence <= last:
                continue
            last = advance(last, event)
            yield event
            if event.type in final_types:
                return
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


async def to_sse_stream(
    events: AsyncIterator[StreamEvent | None],
) -> AsyncIterator[ServerSentEvent]:
    """Write events as SSE; a quiet interval becomes a heartbeat comment."""
    async with aclosing(events):
        async for event in events:
            if event is None:
                yield ServerSentEvent(comment=HEARTBEAT_COMMENT)
            else:
                yield to_sse(event)


def follow(
    redis: Redis,
    channel: str,
    replay: Replay,
    after: int,
    final_types: Collection[str],
    heartbeat_seconds: float | None = None,
) -> AsyncIterator[ServerSentEvent]:
    """Stream a job's events to a client over SSE; see ``follow_events``."""
    return to_sse_stream(
        follow_events(redis, channel, replay, after, final_types, heartbeat_seconds)
    )
