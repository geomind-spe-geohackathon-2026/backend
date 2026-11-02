import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

Operation = Callable[..., Awaitable[Any]]


class LoopBridgeError(RuntimeError):
    """A blocking store call was made from the event loop it needs."""


class LoopBridge:
    """Run database work on the worker's event loop from the threads geomind uses.

    geomind calls its store and workspace synchronously from worker threads while the
    event loop is free; each call opens a session of its own, so calls never share one.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.loop = loop
        self.factory = factory

    def call(self, operation: Operation, *arguments: Any) -> Any:
        """Await ``operation(session, *arguments)`` on the loop; return its result."""
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            raise LoopBridgeError("called inside its own event loop; use a thread")
        future = asyncio.run_coroutine_threadsafe(
            self.run(operation, arguments),
            self.loop,
        )
        return future.result()

    async def run(self, operation: Operation, arguments: tuple[Any, ...]) -> Any:
        async with self.factory() as session:
            return await operation(session, *arguments)
