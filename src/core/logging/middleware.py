from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware

from fastapi import Request
from src.core.logging.logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("%s %s failed", request.method, request.url.path)
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "%s %s %s %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
