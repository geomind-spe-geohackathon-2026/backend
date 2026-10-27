from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.core.clients import close_clients, open_clients
from src.core.logging.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting application")
    open_clients(app)
    try:
        yield
    finally:
        await close_clients(app)
        logger.info("Application stopped")
