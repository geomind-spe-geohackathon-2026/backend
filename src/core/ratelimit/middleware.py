import hashlib

from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from fastapi import Request
from src.core.clients.redis.repositories.rate_limit import RateLimitRepository
from src.core.ratelimit.errors import RateLimitExceededError
from src.core.settings import settings


def client_key(request: Request) -> str:
    """Return the bucket of a request: its access token, else the visitor's address.

    One bucket per user made every browser signed in as the same user share 100 requests a
    minute, and pages showed only "Rate limit exceeded" (QA-024). A verified token (the auth
    middleware set ``user_id``) is one sign-in, so each browser has its own bucket. Behind the
    Cloudflare tunnel ``request.client`` is the proxy for everyone, so the visitor's address is
    Cloudflare's ``CF-Connecting-IP``.
    """
    user_id = getattr(request.state, "user_id", None)
    authorization = request.headers.get("authorization", "")
    if user_id and authorization.lower().startswith("bearer "):
        token = hashlib.sha256(authorization[7:].strip().encode()).hexdigest()[:32]
        return f"token:{token}"
    if user_id:
        return f"user:{user_id}"
    address = request.headers.get("cf-connecting-ip") or (
        request.client.host if request.client else "unknown"
    )
    return f"ip:{address}"


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

        client = client_key(request)

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
