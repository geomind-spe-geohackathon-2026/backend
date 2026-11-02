from collections.abc import Callable
from typing import Annotated, Any

from kombu.exceptions import OperationalError

from fastapi import Depends
from src.core.assistant.errors import QueueUnavailableError

Enqueue = Callable[..., None]


def enqueue_task(name: str, *args: Any) -> None:
    """Send a Celery task by name; blocking, so call it in a thread.

    The Celery app imports every feature's tasks, so it is imported here and the task
    is sent by name, which also keeps features from importing each other's tasks.
    """
    from src.celery import app

    try:
        app.send_task(name, args=args)
    except OperationalError as error:
        raise QueueUnavailableError("The task queue is not reachable") from error


def get_enqueue() -> Enqueue:
    return enqueue_task


EnqueueDependency = Annotated[Enqueue, Depends(get_enqueue)]
