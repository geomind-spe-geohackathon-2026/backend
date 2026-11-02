import asyncio

import fakeredis
import pytest
from fastapi.sse import EventSourceResponse
from httpx import ASGITransport, AsyncClient

from fastapi import Depends, FastAPI
from src.core.errors import ErrorMiddleware, include_exception_handlers
from src.core.sse.events import StreamEvent, channel_name
from src.core.sse.follow import follow, last_event_id
from src.core.sse.publish import publish_event_async

CHANNEL = channel_name("run", "r1")
FINAL = ("run.finished",)


def stored(*sequences: int) -> list[StreamEvent]:
    return [StreamEvent("step.started", {"index": n}, n) for n in sequences]


@pytest.fixture
async def redis():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


def stream_app(redis, replay, heartbeat: float = 5.0) -> FastAPI:
    app = FastAPI()
    include_exception_handlers(app)
    app.add_middleware(ErrorMiddleware)

    @app.get("/events", response_class=EventSourceResponse)
    async def events(after: int = Depends(last_event_id)):
        async for item in follow(redis, CHANNEL, replay, after, FINAL, heartbeat):
            yield item

    return app


def client_for(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def ids(body: str) -> list[str]:
    return [line[4:] for line in body.splitlines() if line.startswith("id: ")]


async def test_stored_events_replay_after_last_event_id_then_end(redis) -> None:
    calls = []

    async def replay(after: int) -> list[StreamEvent]:
        calls.append(after)
        return [*stored(2, 3), StreamEvent("run.finished", {"status": "done"}, 4)]

    async with client_for(stream_app(redis, replay)) as client:
        response = await client.get("/events", headers={"Last-Event-ID": "1"})

    assert calls == [1]
    assert response.headers["content-type"].startswith("text/event-stream")
    assert ids(response.text) == ["2", "3", "4"]
    assert "event: run.finished" in response.text
    assert 'data: {"status": "done"}' in response.text


async def test_a_new_stream_replays_from_the_start(redis) -> None:
    calls = []

    async def replay(after: int) -> list[StreamEvent]:
        calls.append(after)
        return [StreamEvent("run.finished", {}, 0)]

    async with client_for(stream_app(redis, replay)) as client:
        await client.get("/events")

    assert calls == [-1]


async def test_subscription_comes_first_and_duplicates_are_dropped(redis) -> None:
    async def replay(after: int) -> list[StreamEvent]:
        await publish_event_async(redis, CHANNEL, stored(3)[0])
        await publish_event_async(
            redis, CHANNEL, StreamEvent("text.delta", {"text": "a"})
        )
        await publish_event_async(redis, CHANNEL, StreamEvent("run.finished", {}, 4))
        return stored(2, 3)

    async with client_for(stream_app(redis, replay)) as client:
        response = await client.get("/events")

    assert ids(response.text) == ["2", "3", "4"]
    assert response.text.count("event: text.delta") == 1


async def test_idle_stream_sends_heartbeat_comments(redis) -> None:
    async def replay(after: int) -> list[StreamEvent]:
        return []

    async def finish_later() -> None:
        await asyncio.sleep(0.3)
        await publish_event_async(redis, CHANNEL, StreamEvent("run.finished", {}, 1))

    task = asyncio.create_task(finish_later())
    async with client_for(stream_app(redis, replay, heartbeat=0.05)) as client:
        response = await client.get("/events")
    await task

    assert response.text.count(": heartbeat") >= 2
    assert ids(response.text) == ["1"]


async def test_subscription_is_closed_when_the_stream_ends(redis) -> None:
    async def replay(after: int) -> list[StreamEvent]:
        return [StreamEvent("run.finished", {}, 1)]

    async with client_for(stream_app(redis, replay)) as client:
        await client.get("/events")

    assert (await redis.pubsub_numsub(CHANNEL))[0][1] == 0


async def test_bad_last_event_id_is_a_validation_error(redis) -> None:
    async def replay(after: int) -> list[StreamEvent]:
        return []

    async with client_for(stream_app(redis, replay)) as client:
        response = await client.get("/events", headers={"Last-Event-ID": "abc"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
