from collections.abc import AsyncIterator, Awaitable, Callable

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from src.core.clients.postgres import models  # noqa: F401
from src.core.clients.postgres.client import Base
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.security.jwt import create_token_pair
from src.core.security.passwords import hash_password
from src.fastapi import app

PASSWORD = "correct-password"
PASSWORD_HASH = hash_password(PASSWORD)


def bearer(user: User) -> dict[str, str]:
    token = create_token_pair(user.id).access_token
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    event.listen(
        engine.sync_engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
async def redis() -> AsyncIterator[fakeredis.FakeAsyncRedis]:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    redis: fakeredis.FakeAsyncRedis,
) -> AsyncIterator[AsyncClient]:
    """Serve the real application on SQLite and fakeredis, without its lifespan."""
    app.state.postgres_session_factory = session_factory
    app.state.redis = redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.state.postgres_session_factory = None
    app.state.redis = None


@pytest.fixture
def make_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[User]]:
    async def create(
        email: str = "member@example.com",
        role: str = "member",
        active: bool = True,
    ) -> User:
        async with session_factory() as session:
            repository = UserRepository(session)
            name = email.partition("@")[0]
            user = await repository.create(email, PASSWORD_HASH, name=name, role=role)
            return await repository.update(user, {"active": active})

    return create


@pytest.fixture
def make_project(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[Project]]:
    async def create(owner: User, name: str = "Doublet") -> Project:
        async with session_factory() as session:
            return await ProjectRepository(session).create(name, owner.id)

    return create
