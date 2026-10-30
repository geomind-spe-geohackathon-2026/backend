from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.core.clients import close_clients, open_clients
from src.core.logging.logger import get_logger
from src.core.security.bootstrap import ensure_first_admin

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting application")
    open_clients(app)
    await ensure_first_admin(app.state.postgres_session_factory)
    try:
        yield
    finally:
        await close_clients(app)
        logger.info("Application stopped")
