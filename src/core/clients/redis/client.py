from typing import Annotated

from redis.asyncio import Redis

from fastapi import Depends, FastAPI, Request
from src.core.clients.errors import ClientNotInitializedError
from src.core.settings import settings


def create_redis_client() -> Redis:
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


def open_redis(app: FastAPI) -> None:
    app.state.redis = create_redis_client()


async def close_redis(app: FastAPI) -> None:
    client: Redis | None = getattr(app.state, "redis", None)
    if client is not None:
        await client.aclose()
    app.state.redis = None


def get_redis(request: Request) -> Redis:
    client: Redis | None = getattr(request.app.state, "redis", None)
    if client is None:
        raise ClientNotInitializedError("Redis is not initialized")
    return client


RedisClient = Annotated[Redis, Depends(get_redis)]
