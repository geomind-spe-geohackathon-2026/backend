from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import MaxRetryError

from fastapi import FastAPI, Request
from src.core.clients.errors import ClientNotInitializedError
from src.core.logging.logger import get_logger
from src.core.settings import settings

BUCKET_TAKEN_CODES = {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}

logger = get_logger(__name__)


def create_minio_client() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def ensure_bucket(client: Minio, bucket: str) -> None:
    """Create the bucket if it is not there; another process may create it first."""
    if client.bucket_exists(bucket):
        return
    try:
        client.make_bucket(bucket)
    except S3Error as error:
        if error.code not in BUCKET_TAKEN_CODES:
            raise


def prepare_bucket(client: Minio) -> None:
    """Create the bucket at startup; a storage that is down must not stop the app."""
    try:
        ensure_bucket(client, settings.MINIO_BUCKET_NAME)
    except (S3Error, MaxRetryError, OSError) as error:
        logger.warning("The storage bucket was not prepared: %s", error)


def open_minio(app: FastAPI) -> None:
    app.state.minio = create_minio_client()
    prepare_bucket(app.state.minio)


def close_minio(app: FastAPI) -> None:
    app.state.minio = None


def get_minio(request: Request) -> Minio:
    client: Minio | None = getattr(request.app.state, "minio", None)
    if client is None:
        raise ClientNotInitializedError("MinIO is not initialized")
    return client
