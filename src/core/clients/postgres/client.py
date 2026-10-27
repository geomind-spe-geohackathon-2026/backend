from collections.abc import AsyncIterator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

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
