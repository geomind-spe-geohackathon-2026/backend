import asyncio
import json

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from fastapi import FastAPI, WebSocket
from src.core.socket.relay import (
    CLOSE_BAD_HELLO,
    read_hello,
    relay,
    to_frame,
)
from src.core.sse.events import StreamEvent


def relay_app(events, seen: list[str] | None = None) -> FastAPI:
    app = FastAPI()

    @app.websocket("/stream")
    async def stream(websocket: WebSocket) -> None:
        await websocket.accept()
        hello = await read_hello(websocket)
        if hello is None:
            return
        await relay(websocket, events(hello.after, seen))

    return app


async def two_events(after, seen):
    yield StreamEvent("usage", {"after": after}, 3)
    yield None
    yield StreamEvent("text.delta", {"text": "سلام"})


def test_frames_keep_persian_text_and_carry_the_sequence() -> None:
    frame = to_frame(StreamEvent("text.delta", {"text": "سلام"}, 4))
    assert "سلام" in frame
    assert json.loads(frame) == {
        "event": "text.delta",
        "id": 4,
        "data": {"text": "سلام"},
    }


def test_a_heartbeat_is_a_frame_without_data() -> None:
    assert json.loads(to_frame(None)) == {"event": "heartbeat"}


def test_events_arrive_in_order_then_the_socket_closes_normally() -> None:
    with TestClient(relay_app(two_events)).websocket_connect("/stream") as socket:
        socket.send_text(json.dumps({"token": "t", "after": 2}))
        frames = [socket.receive_json() for _ in range(3)]
        closing = socket.receive()
    assert [frame["event"] for frame in frames] == [
        "usage",
        "heartbeat",
        "text.delta",
    ]
    assert frames[0]["data"] == {"after": 2}
    assert frames[2]["id"] is None
    assert closing == {"type": "websocket.close", "code": 1000, "reason": ""}


def test_a_bad_hello_closes_the_socket() -> None:
    with TestClient(relay_app(two_events)).websocket_connect("/stream") as socket:
        socket.send_text("not json")
        closing = socket.receive()
    assert closing["code"] == CLOSE_BAD_HELLO


class LeavingSocket:
    """A socket whose client leaves once the first event reached it."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.left = asyncio.Event()

    async def send_text(self, text: str) -> None:
        self.sent.append(text)
        self.left.set()

    async def receive(self) -> dict:
        await self.left.wait()
        return {"type": "websocket.disconnect"}

    async def close(self, code: int) -> None:
        raise AssertionError("a socket whose client left is not closed again")


async def test_the_stream_stops_when_the_client_leaves() -> None:
    seen: list[str] = []

    async def endless(after, record):
        try:
            while True:
                yield StreamEvent("usage", {}, 1)
                await asyncio.sleep(0.01)
        finally:
            record.append("closed")

    socket = LeavingSocket()
    await relay(socket, endless(-1, seen))

    assert seen == ["closed"]
    assert len(socket.sent) >= 1


def test_a_failing_stream_closes_with_an_error_code() -> None:
    async def broken(after, seen):
        yield StreamEvent("usage", {}, 1)
        raise RuntimeError("redis went away")

    with TestClient(relay_app(broken)).websocket_connect("/stream") as socket:
        socket.send_text(json.dumps({"token": "t"}))
        socket.receive_json()
        closing = socket.receive()
    assert closing["code"] == 1011


class LeftSocket:
    """A socket whose client left just as the last event went out."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def receive(self) -> dict:
        await asyncio.sleep(1)
        return {"type": "websocket.disconnect"}

    async def close(self, code: int) -> None:
        raise WebSocketDisconnect(code=1006)


async def test_a_client_that_left_at_the_end_raises_nothing() -> None:
    async def one(after, seen):
        yield StreamEvent("run.finished", {"status": "done"}, 1)

    socket = LeftSocket()
    await relay(socket, one(-1, None))
    assert len(socket.sent) == 1
