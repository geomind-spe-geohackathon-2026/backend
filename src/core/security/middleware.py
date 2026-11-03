from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from fastapi import Request
from src.core.clients.redis.repositories.revoked_access_token import (
    RevokedAccessTokenRepository,
)
from src.core.security.errors import (
    AuthenticationUnavailableError,
    UnauthorizedError,
)
from src.core.security.jwt import AccessTokenClaims, verify_access_token
from src.core.security.paths import is_public_path


async def verify_live_token(
    authorization: str,
    redis: Redis | None,
) -> tuple[str, AccessTokenClaims]:
    """Return a valid access token and its claims, refusing one that was revoked."""
    access_token, claims = verify_access_token(authorization)
    if redis is None:
        raise AuthenticationUnavailableError("Authentication service is unavailable")
    repository = RevokedAccessTokenRepository(redis)
    try:
        revoked = await repository.is_revoked(claims.token_id)
    except RedisError:
        raise AuthenticationUnavailableError(
            "Authentication service is unavailable"
        ) from None
    if revoked:
        raise UnauthorizedError("Token has been revoked")
    return access_token, claims


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or not path.startswith("/api/v1/")
            or is_public_path(path)
        ):
            return await call_next(request)

        request.state.access_token = None
        authorization = request.headers.get("Authorization", "")
        redis: Redis | None = getattr(request.app.state, "redis", None)
        access_token, claims = await verify_live_token(authorization, redis)

        request.state.access_token = access_token
        request.state.access_token_claims = claims
        request.state.user_id = claims.subject
        return await call_next(request)
