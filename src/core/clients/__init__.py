from fastapi import FastAPI
from src.core.clients.chromadb.client import close_chromadb, open_chromadb
from src.core.clients.influxdb.client import close_influxdb, open_influxdb
from src.core.clients.minio.client import close_minio, open_minio
from src.core.clients.openrouter.client import close_openrouter, open_openrouter
from src.core.clients.postgres.client import close_postgres, open_postgres
from src.core.clients.redis.client import close_redis, open_redis


def open_clients(app: FastAPI) -> None:
    open_postgres(app)
    open_redis(app)
    open_minio(app)
    open_chromadb(app)
    open_influxdb(app)
    open_openrouter(app)


async def close_clients(app: FastAPI) -> None:
    await close_openrouter(app)
    await close_influxdb(app)
    await close_chromadb(app)
    await close_redis(app)
    close_minio(app)
    await close_postgres(app)
