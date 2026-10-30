from celery import Celery
from src.api import TASK_MODULES
from src.core.settings import settings

app = Celery(
    settings.APP_NAME,
    broker=settings.CELERY_BROKER_URL,
    include=TASK_MODULES,
)
app.conf.update(
    enable_utc=True,
    task_ignore_result=True,
    timezone="UTC",
)


def run() -> None:
    app.worker_main(["worker", "--loglevel=INFO"])
