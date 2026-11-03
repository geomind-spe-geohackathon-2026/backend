import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Any

from pydantic import BaseModel, ValidationError
from starlette.websockets import WebSocketDisconnect

from fastapi import WebSocket
from src.core.logging.logger import get_logger
from src.core.sse.events import StreamEvent

CLOSE_NORMAL = 1000
CLOSE_FAILED = 1011
CLOSE_BAD_HELLO = 4400
CLOSE_UNAUTHORIZED = 4401
CLOSE_NOT_FOUND = 4404
HELLO_SECONDS = 10.0
HEARTBEAT_EVENT = "heartbeat"
NO_EVENT = -1

logger = get_logger(__name__)


class Hello(BaseModel):
    """The first message of a socket; a browser cannot set headers on a WebSocket.

    The token travels here and not in the URL, which proxies and logs would keep.
    """

    token: str
    after: int = NO_EVENT


async def read_hello(websocket: WebSocket) -> Hello | None:
    """Return the client's first message, or close the socket and return ``None``."""
    try:
        text = await asyncio.wait_for(websocket.receive_text(), HELLO_SECONDS)
        return Hello.model_validate_json(text)
    except WebSocketDisconnect:
        return None
    except (TimeoutError, ValidationError):
        await websocket.close(CLOSE_BAD_HELLO)
        return None


def to_frame(event: StreamEvent | None) -> str:
    """Write an event as one text frame; ``None`` is a heartbeat."""
    body: dict[str, Any] = {"event": HEARTBEAT_EVENT}
    if event is not None:
        body = {"event": event.type, "id": event.sequence, "data": event.data}
    return json.dumps(body, ensure_ascii=False)


async def send_all(
    websocket: WebSocket,
    events: AsyncIterator[StreamEvent | None],
) -> None:
    async with aclosing(events):
        async for event in events:
            await websocket.send_text(to_frame(event))


async def wait_for_disconnect(websocket: WebSocket) -> None:
    """Return when the client leaves; anything it sends after its hello is ignored."""
    while (await websocket.receive())["type"] != "websocket.disconnect":
        continue


async def relay(
    websocket: WebSocket,
    events: AsyncIterator[StreamEvent | None],
) -> None:
    """Send events until they end or the client leaves, then close the socket."""
    sender = asyncio.create_task(send_all(websocket, events))
    watcher = asyncio.create_task(wait_for_disconnect(websocket))
    done, _ = await asyncio.wait({sender, watcher}, return_when=asyncio.FIRST_COMPLETED)
    for task in (sender, watcher):
        task.cancel()
    await asyncio.gather(sender, watcher, return_exceptions=True)
    if sender not in done or sender.cancelled():
        return
    failure = sender.exception()
    if isinstance(failure, WebSocketDisconnect):
        return
    if failure is not None:
        logger.error("A socket stream failed", exc_info=failure)
    code = CLOSE_NORMAL if failure is None else CLOSE_FAILED
    try:
        await websocket.close(code)
    except (RuntimeError, WebSocketDisconnect):
        logger.info("The client left before the socket closed")
