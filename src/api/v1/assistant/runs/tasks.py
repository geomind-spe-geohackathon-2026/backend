import asyncio
from typing import Any
from uuid import UUID

from celery import shared_task
from src.api.v1.assistant.runs import execution

TASK_MODULES = (__name__,)


@shared_task(name="assistant.runs.start")
def start(run_id: str) -> None:
    """Run a queued assistant run."""
    asyncio.run(execution.start_run(UUID(run_id)))


@shared_task(name="assistant.runs.resume")
def resume(
    run_id: str,
    request_id: str | None,
    answer: dict[str, Any] | None,
) -> None:
    """Continue a waiting run with the user's answer, or end it after a cancel."""
    asyncio.run(execution.resume_run(UUID(run_id), request_id, answer))
