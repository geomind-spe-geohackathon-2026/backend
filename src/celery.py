from celery import Celery
from src.api import TASK_MODULES
from src.core.settings import settings

app = Celery(
    settings.APP_NAME,
    broker=settings.CELERY_BROKER_URL,
    include=TASK_MODULES,
    task_cls="src.core.jobs.task:BaseTask",
)
app.conf.update(
    enable_utc=True,
    task_ignore_result=True,
    task_soft_time_limit=settings.TASK_SOFT_TIME_LIMIT_SECONDS,
    task_time_limit=settings.TASK_TIME_LIMIT_SECONDS,
    timezone="UTC",
)


def run() -> None:
    app.worker_main(["worker", "--loglevel=INFO"])
