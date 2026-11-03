from celery.signals import worker_ready

from celery import Celery
from src.api import TASK_MODULES
from src.api.v1.assistant.runs.adapters.session import check_models
from src.core.clients.minio.client import create_minio_client, prepare_bucket
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


@worker_ready.connect
def prepare_storage(**_details: object) -> None:
    prepare_bucket(create_minio_client())


def run() -> None:
    check_models()
    app.worker_main(["worker", "--loglevel=INFO"])
