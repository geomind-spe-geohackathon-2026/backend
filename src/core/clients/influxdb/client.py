import httpx

from fastapi import FastAPI, Request
from src.core.clients.errors import ClientNotInitializedError
from src.core.settings import settings


def create_influxdb_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.INFLUXDB_URL,
        headers={"Authorization": f"Token {settings.INFLUXDB_TOKEN}"},
    )


def open_influxdb(app: FastAPI) -> None:
    app.state.influxdb = create_influxdb_client()


async def close_influxdb(app: FastAPI) -> None:
    client: httpx.AsyncClient | None = getattr(app.state, "influxdb", None)
    if client is not None:
        await client.aclose()
    app.state.influxdb = None


def get_influxdb(request: Request) -> httpx.AsyncClient:
    client: httpx.AsyncClient | None = getattr(request.app.state, "influxdb", None)
    if client is None:
        raise ClientNotInitializedError("InfluxDB is not initialized")
    return client
