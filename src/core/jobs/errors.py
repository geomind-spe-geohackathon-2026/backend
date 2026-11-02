from src.core.errors import AppError


class JobCancelledError(AppError):
    """Raised inside a job when its cancellation flag is set."""

    code = "cancelled"

    def __init__(self, job_id: str) -> None:
        super().__init__("Job was cancelled", details={"job": job_id})
