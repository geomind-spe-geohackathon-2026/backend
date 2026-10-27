from datetime import UTC, datetime
from typing import Annotated

from redis.asyncio import Redis

from fastapi import Depends
from src.core.clients.redis.client import get_redis
from src.core.clients.redis.models.revoked_access_token import RevokedAccessToken
from src.core.clients.redis.repositories.base import BaseRedisRepository

RedisClient = Annotated[Redis, Depends(get_redis)]


class RevokedAccessTokenRepository(BaseRedisRepository):
    key_prefix = "revoked_access_token"

    async def is_revoked(self, token_id: str) -> bool:
        return await self.exists(token_id)

    async def revoke(self, revoked_access_token: RevokedAccessToken) -> None:
        remaining = revoked_access_token.expires_at - datetime.now(UTC)
        ttl = max(int(remaining.total_seconds()), 1)
        await self.set(
            revoked_access_token.token_id,
            "1",
            expires_in=ttl,
        )


def get_revoked_access_token_repository(
    redis: RedisClient,
) -> RevokedAccessTokenRepository:
    return RevokedAccessTokenRepository(redis)
