from collections.abc import Awaitable, Callable, Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.assistant.errors import QueueUnavailableError
from src.core.assistant.queue import get_enqueue
from src.core.clients.postgres.models.chat import Chat
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.chat import ChatRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.fastapi import app


class Queue:
    """A task queue for tests: it records what would be sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[Any, ...]] = []
        self.down = False

    def __call__(self, name: str, *args: Any) -> None:
        if self.down:
            raise QueueUnavailableError("The task queue is not reachable")
        self.sent.append((name, *args))


@pytest.fixture
def queue() -> Iterator[Queue]:
    recorder = Queue()
    app.dependency_overrides[get_enqueue] = lambda: recorder
    yield recorder
    app.dependency_overrides.pop(get_enqueue, None)


@pytest.fixture
def make_chat(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[Chat]]:
    async def create(project: Project, owner: User, title: str = "Sizing") -> Chat:
        async with session_factory() as session:
            return await ChatRepository(session).create(project.id, title, owner.id)

    return create


@pytest.fixture
def make_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[Run]]:
    async def create(
        chat: Chat,
        owner: User,
        status: str = "queued",
        values: dict[str, Any] | None = None,
        content: str = "Size the plant",
    ) -> Run:
        async with session_factory() as session:
            runs = RunRepository(session)
            run = await runs.create(uuid4(), chat.id, chat.project_id, owner.id)
            await MessageRepository(session).add(chat.id, "user", content, run.id)
            return await runs.update(run, {"status": status, **(values or {})})

    return create


def run_url(run_id: UUID, suffix: str = "") -> str:
    return f"/api/v1/assistant/runs/{run_id}{suffix}"
