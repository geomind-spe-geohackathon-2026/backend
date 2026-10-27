from redis.asyncio import Redis


class BaseRedisRepository:
    key_prefix: str

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    def key(self, identifier: str) -> str:
        return f"{self.key_prefix}:{identifier}"

    async def get(self, identifier: str) -> str | None:
        return await self.redis.get(self.key(identifier))

    async def set(
        self,
        identifier: str,
        value: str,
        expires_in: int | None = None,
    ) -> None:
        await self.redis.set(self.key(identifier), value, ex=expires_in)

    async def exists(self, identifier: str) -> bool:
        return bool(await self.redis.exists(self.key(identifier)))

    async def delete(self, identifier: str) -> bool:
        return bool(await self.redis.delete(self.key(identifier)))
