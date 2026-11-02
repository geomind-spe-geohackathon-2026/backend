from src.core.clients.redis.repositories.job import JobRepository
from src.core.settings import settings

TERMINATE_TASK = "jobs.terminate"


async def request_cancel(jobs: JobRepository, job_id: str) -> None:
    """Set the flag a running job reads between its steps."""
    await jobs.request_cancel(job_id, settings.JOB_STATE_TTL_SECONDS)


def terminate_later(task_id: str) -> None:
    """Queue the kill of a cancelled task, for one that never reaches a flag check."""
    from src.celery import app

    delay = settings.JOB_CANCEL_GRACE_SECONDS
    app.send_task(TERMINATE_TASK, args=[task_id], countdown=delay)


def terminate(task_id: str) -> None:
    """Stop a task that cannot check a flag: revoke it and kill its worker process.

    The Celery app is imported here because it imports every feature's tasks, and a
    feature's services import this module.
    """
    from src.celery import app

    app.control.revoke(task_id, terminate=True, signal="SIGTERM")
