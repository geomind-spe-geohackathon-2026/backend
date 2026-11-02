from collections.abc import Iterator
from io import BytesIO

import pytest

from src.core.clients.minio.client import get_minio
from src.fastapi import app


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        return None

    def release_conn(self) -> None:
        return None


class FakeMinio:
    """The few MinIO calls the workspace makes, kept in memory."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def bucket_exists(self, bucket: str) -> bool:
        return True

    def put_object(self, bucket: str, key: str, data: BytesIO, length: int) -> None:
        self.objects[key] = data.read()

    def get_object(self, bucket: str, key: str) -> FakeResponse:
        return FakeResponse(self.objects[key])

    def remove_object(self, bucket: str, key: str) -> None:
        del self.objects[key]


@pytest.fixture
def minio() -> Iterator[FakeMinio]:
    fake = FakeMinio()
    app.dependency_overrides[get_minio] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_minio)


@pytest.fixture(autouse=True)
def use_fake_minio(minio: FakeMinio) -> None:
    return None
