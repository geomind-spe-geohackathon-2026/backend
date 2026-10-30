from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from fastapi import FastAPI, Request
from src.core.clients.errors import ClientNotInitializedError
from src.core.settings import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UtcDateTime(TypeDecorator):
    """Timezone-aware datetime that is always stored and returned in UTC."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_postgres_client() -> AsyncEngine:
    return create_async_engine(
        settings.POSTGRES_URL,
        pool_pre_ping=True,
        pool_size=settings.POSTGRES_POOL_SIZE,
        max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    )


def open_postgres(app: FastAPI) -> None:
    engine = create_postgres_client()
    app.state.postgres = engine
    app.state.postgres_session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def close_postgres(app: FastAPI) -> None:
    engine: AsyncEngine | None = getattr(app.state, "postgres", None)
    if engine is not None:
        await engine.dispose()
    app.state.postgres = None
    app.state.postgres_session_factory = None


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = getattr(request.app.state, "postgres_session_factory", None)
    if session_factory is None:
        raise ClientNotInitializedError("PostgreSQL is not initialized")
    async with session_factory() as session:
        yield session
