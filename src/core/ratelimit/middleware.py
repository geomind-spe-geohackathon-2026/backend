from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from fastapi import Request
from src.core.clients.redis.repositories.rate_limit import RateLimitRepository
from src.core.ratelimit.errors import RateLimitExceededError
from src.core.settings import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if (
            request.method == "OPTIONS"
            or not request.url.path.startswith("/api/")
            or request.url.path == "/api/v1/system/health"
        ):
            return await call_next(request)

        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        client_ip = request.client.host if request.client else "unknown"
        client = f"user:{user_id}" if user_id else f"ip:{client_ip}"

        try:
            rate_limit = await RateLimitRepository(redis).increment(
                identifier=client,
                limit=settings.RATE_LIMIT_REQUESTS,
                window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
            )
        except RedisError:
            return await call_next(request)

        headers = {
            "X-RateLimit-Limit": str(rate_limit.limit),
            "X-RateLimit-Remaining": str(rate_limit.remaining),
        }
        if rate_limit.exceeded:
            headers["Retry-After"] = str(rate_limit.retry_after)
            raise RateLimitExceededError("Rate limit exceeded", headers=headers)

        response = await call_next(request)
        response.headers.update(headers)
        return response
