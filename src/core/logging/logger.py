import logging

from src.core.settings import settings

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    logging.basicConfig(level=settings.APP_LOG_LEVEL, format=LOG_FORMAT)
    logging.getLogger("swarmax").setLevel(settings.APP_LOG_LEVEL)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"swarmax.{name}")
