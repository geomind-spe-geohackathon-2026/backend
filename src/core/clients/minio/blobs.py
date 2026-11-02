import asyncio
from io import BytesIO
from typing import Annotated

from minio import Minio
from minio.error import S3Error

from fastapi import Depends, Request
from src.core.clients.minio.client import get_minio
from src.core.settings import settings

MISSING_OBJECT_CODES = {"NoSuchKey", "NoSuchObject"}


class BlobStore:
    """Whole objects in the configured bucket, written and read as bytes."""

    def __init__(self, client: Minio, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def put_sync(self, key: str, data: bytes) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        self.client.put_object(self.bucket, key, BytesIO(data), len(data))

    def get_sync(self, key: str) -> bytes | None:
        try:
            response = self.client.get_object(self.bucket, key)
        except S3Error as error:
            if error.code in MISSING_OBJECT_CODES:
                return None
            raise
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def put(self, key: str, data: bytes) -> None:
        """Write the object, creating the bucket on first use."""
        await asyncio.to_thread(self.put_sync, key, data)

    async def get(self, key: str) -> bytes | None:
        """Return the object's bytes, or ``None`` when there is no such object."""
        return await asyncio.to_thread(self.get_sync, key)


def get_blob_store(request: Request) -> BlobStore:
    return BlobStore(get_minio(request), settings.MINIO_BUCKET_NAME)


BlobStoreDependency = Annotated[BlobStore, Depends(get_blob_store)]
