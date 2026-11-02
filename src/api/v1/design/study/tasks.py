import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from celery import Task, shared_task
from src.api.v1.design.study import services
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.minio.client import create_minio_client
from src.core.clients.postgres.client import create_postgres_client
from src.core.jobs import control
from src.core.settings import settings

TASK_MODULES = (__name__,)


async def execute(task: Task, study_id: UUID) -> None:
    """Open this worker's own database and MinIO access and run the study."""
    engine = create_postgres_client()
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with sessions() as session:
            stores = services.Stores.open(session)
            blobs = BlobStore(create_minio_client(), settings.MINIO_BUCKET_NAME)
            await services.run_study(
                study_id, stores, blobs, task.report, task.jobs.is_cancel_requested
            )
    finally:
        await engine.dispose()


@shared_task(bind=True, name="design.study.run")
def run_study(self: Task, study_id: str) -> None:
    asyncio.run(execute(self, UUID(study_id)))


@shared_task(name=control.TERMINATE_TASK)
def terminate_task(task_id: str) -> None:
    """Kill a cancelled task that is still running after the grace time."""
    control.terminate(task_id)


def enqueue(study_id: UUID) -> str:
    """Queue the study for a worker and return the Celery task id."""
    return run_study.delay(str(study_id)).id
