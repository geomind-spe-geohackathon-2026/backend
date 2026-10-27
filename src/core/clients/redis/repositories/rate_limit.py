from time import time

from src.core.clients.redis.models.rate_limit import RateLimit
from src.core.clients.redis.repositories.base import BaseRedisRepository


class RateLimitRepository(BaseRedisRepository):
    key_prefix = "rate_limit"

    async def increment(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimit:
        now = int(time())
        bucket = now // window_seconds
        key = self.key(f"{identifier}:{bucket}")
        requests = await self.redis.incr(key)
        if requests == 1:
            await self.redis.expire(key, window_seconds)
        return RateLimit(
            limit=limit,
            requests=requests,
            retry_after=window_seconds - now % window_seconds,
        )
