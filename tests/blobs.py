"""An in-memory object store for tests, so none of them reaches MinIO."""

from collections.abc import Iterator

import pytest

from src.core.clients.minio.blobs import BlobStore, get_blob_store
from src.fastapi import app


class MemoryBlobStore(BlobStore):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)


@pytest.fixture
def blobs() -> Iterator[MemoryBlobStore]:
    store = MemoryBlobStore()
    app.dependency_overrides[get_blob_store] = lambda: store
    yield store
    app.dependency_overrides.pop(get_blob_store)
