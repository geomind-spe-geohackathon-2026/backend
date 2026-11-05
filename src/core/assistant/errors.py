from starlette import status

from src.core.errors import AppError, ConflictError, NotFoundError


class ChatNotFoundError(NotFoundError):
    code = "chat_not_found"


class RunNotFoundError(NotFoundError):
    code = "run_not_found"


class CallNotFoundError(NotFoundError):
    code = "call_not_found"


class RunNotWaitingError(ConflictError):
    code = "run_not_waiting"


class QueueUnavailableError(AppError):
    """The task queue refused a job; nothing was started."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "unavailable"
