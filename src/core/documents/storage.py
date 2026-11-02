from io import BytesIO

from minio import Minio

from src.core.settings import settings


def store_object(client: Minio, key: str, data: bytes) -> None:
    """Write bytes under a key, creating the bucket on first use."""
    bucket = settings.MINIO_BUCKET_NAME
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    client.put_object(bucket, key, BytesIO(data), len(data))


def read_object(client: Minio, key: str) -> bytes:
    """Read the bytes stored under a key."""
    response = client.get_object(settings.MINIO_BUCKET_NAME, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def remove_object(client: Minio, key: str) -> None:
    """Delete the bytes stored under a key."""
    client.remove_object(settings.MINIO_BUCKET_NAME, key)
