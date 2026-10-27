import httpx

from fastapi import FastAPI, Request
from src.core.clients.errors import ClientNotInitializedError
from src.core.settings import settings


def create_openrouter_client() -> httpx.AsyncClient:
    headers = {}
    if settings.OPENROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OPENROUTER_API_KEY}"
    return httpx.AsyncClient(base_url=settings.OPENROUTER_BASE_URL, headers=headers)


def open_openrouter(app: FastAPI) -> None:
    app.state.openrouter = create_openrouter_client()


async def close_openrouter(app: FastAPI) -> None:
    client: httpx.AsyncClient | None = getattr(app.state, "openrouter", None)
    if client is not None:
        await client.aclose()
    app.state.openrouter = None


def get_openrouter(request: Request) -> httpx.AsyncClient:
    client: httpx.AsyncClient | None = getattr(request.app.state, "openrouter", None)
    if client is None:
        raise ClientNotInitializedError("OpenRouter is not initialized")
    return client
