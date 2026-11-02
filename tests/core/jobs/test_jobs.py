from collections.abc import Iterator
from unittest.mock import patch

import fakeredis
import pytest

from celery import Celery
from src.celery import app as application
from src.core.clients.redis.models.job import JobProgress
from src.core.clients.redis.repositories.job import JobRepository, SyncJobRepository
from src.core.errors import ConflictError
from src.core.jobs import control
from src.core.jobs.errors import JobCancelledError
from src.core.jobs.task import BaseTask

JOB = "job-1"


@pytest.fixture
def server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture
def worker_app(server: fakeredis.FakeServer) -> Iterator[Celery]:
    app = Celery("test", task_cls="src.core.jobs.task:BaseTask")
    app.conf.update(task_always_eager=True, task_eager_propagates=True)
    redis = fakeredis.FakeRedis(server=server, decode_responses=True)
    with patch.object(BaseTask, "_jobs", SyncJobRepository(redis, 60)):
        yield app


def test_application_tasks_use_the_base_task() -> None:
    assert issubclass(application.Task, BaseTask)
    assert application.conf.task_time_limit > application.conf.task_soft_time_limit


async def test_progress_is_visible_to_the_api(worker_app, server) -> None:
    @worker_app.task(bind=True, name="test.progress")
    def work(self, job_id: str) -> None:
        self.report(job_id, 1, 4)
        self.report(job_id, 3, 4)

    work.delay(JOB)

    redis = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    assert await JobRepository(redis).progress(JOB) == JobProgress(done=3, total=4)


async def test_cancel_flag_stops_the_task_between_steps(worker_app, server) -> None:
    @worker_app.task(bind=True, name="test.cancel")
    def work(self, job_id: str) -> None:
        self.check_cancelled(job_id)

    work.delay(JOB)
    redis = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    await control.request_cancel(JobRepository(redis), JOB)

    assert await JobRepository(redis).is_cancel_requested(JOB)
    with pytest.raises(JobCancelledError) as error:
        work.delay(JOB)
    assert error.value.code == "cancelled"


def test_app_errors_are_not_retried(worker_app) -> None:
    calls = []

    @worker_app.task(bind=True, name="test.conflict")
    def work(self) -> None:
        calls.append(1)
        raise ConflictError("Already there")

    with pytest.raises(ConflictError):
        work.delay()

    assert calls == [1]


def test_unknown_job_has_no_progress_and_no_flag(server) -> None:
    jobs = SyncJobRepository(fakeredis.FakeRedis(server=server), 60)

    assert jobs.progress("none") is None
    assert not jobs.is_cancel_requested("none")


def test_clear_removes_progress_and_flag(server) -> None:
    jobs = SyncJobRepository(
        fakeredis.FakeRedis(server=server, decode_responses=True), 60
    )
    jobs.set_progress(JOB, JobProgress(done=1, total=2))

    jobs.clear(JOB)

    assert jobs.progress(JOB) is None


def test_terminate_revokes_the_task_with_terminate() -> None:
    with patch.object(application.control, "revoke") as revoke:
        control.terminate("task-1")

    revoke.assert_called_once_with("task-1", terminate=True, signal="SIGTERM")
