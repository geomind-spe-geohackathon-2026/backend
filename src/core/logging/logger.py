import asyncio
import logging

from src.core.settings import settings

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    logging.basicConfig(level=settings.APP_LOG_LEVEL, format=LOG_FORMAT)
    logging.getLogger("swarmax").setLevel(settings.APP_LOG_LEVEL)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"swarmax.{name}")


class DisconnectFilter(logging.Filter):
    """Drop the pool's traceback for a connection cut because a client went away."""

    def filter(self, record: logging.LogRecord) -> bool:
        error = record.exc_info[0] if record.exc_info else None
        return not (error is not None and issubclass(error, asyncio.CancelledError))


def ignore_client_disconnects() -> None:
    logging.getLogger("sqlalchemy.pool").addFilter(DisconnectFilter())
    logging.getLogger("sqlalchemy.pool.impl.AsyncAdaptedQueuePool").addFilter(
        DisconnectFilter()
    )
