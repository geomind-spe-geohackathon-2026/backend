import json

from redis import Redis

from src.core.clients.redis.client import RedisClient
from src.core.clients.redis.models.job import JobProgress
from src.core.clients.redis.repositories.base import BaseRedisRepository

KEY_PREFIX = "job"


def progress_name(job_id: str) -> str:
    return f"{job_id}:progress"


def cancel_name(job_id: str) -> str:
    return f"{job_id}:cancel"


def encode_progress(progress: JobProgress) -> str:
    return json.dumps({"done": progress.done, "total": progress.total})


def decode_progress(text: str | None) -> JobProgress | None:
    if text is None:
        return None
    data = json.loads(text)
    return JobProgress(done=data["done"], total=data["total"])


class JobRepository(BaseRedisRepository):
    """Progress and cancellation flag of a job, read and written by the API."""

    key_prefix = KEY_PREFIX

    async def progress(self, job_id: str) -> JobProgress | None:
        return decode_progress(await self.get(progress_name(job_id)))

    async def request_cancel(self, job_id: str, expires_in: int) -> None:
        await self.set(cancel_name(job_id), "1", expires_in)

    async def is_cancel_requested(self, job_id: str) -> bool:
        return await self.exists(cancel_name(job_id))


class SyncJobRepository:
    """The same keys for a Celery worker or a worker thread, which cannot await."""

    def __init__(self, redis: Redis, expires_in: int) -> None:
        self.redis = redis
        self.expires_in = expires_in

    def key(self, name: str) -> str:
        return f"{KEY_PREFIX}:{name}"

    def set_progress(self, job_id: str, progress: JobProgress) -> None:
        key = self.key(progress_name(job_id))
        self.redis.set(key, encode_progress(progress), ex=self.expires_in)

    def progress(self, job_id: str) -> JobProgress | None:
        return decode_progress(self.redis.get(self.key(progress_name(job_id))))

    def is_cancel_requested(self, job_id: str) -> bool:
        return bool(self.redis.exists(self.key(cancel_name(job_id))))

    def clear(self, job_id: str) -> None:
        self.redis.delete(
            self.key(progress_name(job_id)),
            self.key(cancel_name(job_id)),
        )


def get_job_repository(redis: RedisClient) -> JobRepository:
    return JobRepository(redis)
