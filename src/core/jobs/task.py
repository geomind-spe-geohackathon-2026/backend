from typing import Any

from redis import Redis

from celery import Task
from src.core.clients.redis.models.job import JobProgress
from src.core.clients.redis.repositories.job import SyncJobRepository
from src.core.errors import AppError
from src.core.jobs.errors import JobCancelledError
from src.core.logging.logger import get_logger
from src.core.settings import settings

logger = get_logger(__name__)


class BaseTask(Task):
    """The base of every task in a feature's ``tasks.py``.

    A task takes ids and small values, loads what it needs and is safe to run twice.
    It reports progress with ``report`` and checks ``check_cancelled`` between steps;
    both go through Redis, keyed by the job id (the study or run id), so the API reads
    them without asking the worker. Transient connection errors retry with a bounded
    backoff; an ``AppError`` never retries. A task sets its own ``name``, for example
    ``design.study.run``.
    """

    autoretry_for = (ConnectionError, TimeoutError)
    dont_autoretry_for = (AppError,)
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True
    max_retries = 5
    acks_late = True
    reject_on_worker_lost = True

    _jobs: SyncJobRepository | None = None

    @property
    def jobs(self) -> SyncJobRepository:
        """Return the Redis access of this worker, opened on first use."""
        if self._jobs is None:
            redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            self._jobs = SyncJobRepository(redis, settings.JOB_STATE_TTL_SECONDS)
        return self._jobs

    def report(self, job_id: str, done: int, total: int) -> None:
        """Publish the progress of a job."""
        self.jobs.set_progress(job_id, JobProgress(done=done, total=total))

    def check_cancelled(self, job_id: str) -> None:
        """Raise ``JobCancelledError`` when cancellation was requested."""
        if self.jobs.is_cancel_requested(job_id):
            raise JobCancelledError(job_id)

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        logger.error("Task %s %s failed: %s", self.name, task_id, exc)
