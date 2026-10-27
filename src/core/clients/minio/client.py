from minio import Minio

from fastapi import FastAPI, Request
from src.core.clients.errors import ClientNotInitializedError
from src.core.settings import settings


def create_minio_client() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def open_minio(app: FastAPI) -> None:
    app.state.minio = create_minio_client()


def close_minio(app: FastAPI) -> None:
    app.state.minio = None


def get_minio(request: Request) -> Minio:
    client: Minio | None = getattr(request.app.state, "minio", None)
    if client is None:
        raise ClientNotInitializedError("MinIO is not initialized")
    return client
