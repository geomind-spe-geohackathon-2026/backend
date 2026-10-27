import httpx

from fastapi import FastAPI, Request
from src.core.clients.errors import ClientNotInitializedError
from src.core.settings import settings


def create_chromadb_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.CHROMADB_URL)


def open_chromadb(app: FastAPI) -> None:
    app.state.chromadb = create_chromadb_client()


async def close_chromadb(app: FastAPI) -> None:
    client: httpx.AsyncClient | None = getattr(app.state, "chromadb", None)
    if client is not None:
        await client.aclose()
    app.state.chromadb = None


def get_chromadb(request: Request) -> httpx.AsyncClient:
    client: httpx.AsyncClient | None = getattr(request.app.state, "chromadb", None)
    if client is None:
        raise ClientNotInitializedError("ChromaDB is not initialized")
    return client
