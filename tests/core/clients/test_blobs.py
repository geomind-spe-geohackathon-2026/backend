import pytest
from minio.error import S3Error

from src.core.clients.minio.blobs import BlobStore


def s3_error(code: str) -> S3Error:
    return S3Error(None, code, "message", "resource", "request", "host")


class Response:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        pass


class FakeMinio:
    def __init__(self, bucket_exists: bool = True) -> None:
        self.has_bucket = bucket_exists
        self.objects: dict[str, bytes] = {}
        self.last: Response | None = None

    def bucket_exists(self, _bucket: str) -> bool:
        return self.has_bucket

    def make_bucket(self, _bucket: str) -> None:
        self.has_bucket = True

    def put_object(self, _bucket: str, key: str, stream, length: int) -> None:
        self.objects[key] = stream.read(length)

    def get_object(self, _bucket: str, key: str) -> Response:
        if key not in self.objects:
            raise s3_error("NoSuchKey")
        self.last = Response(self.objects[key])
        return self.last

    def remove_object(self, _bucket: str, key: str) -> None:
        self.objects.pop(key, None)


async def test_put_then_get_round_trips_and_closes_the_response() -> None:
    client = FakeMinio()
    store = BlobStore(client, "bucket")

    await store.put("a/b", b"data")

    assert await store.get("a/b") == b"data"
    assert client.last.closed


async def test_put_creates_the_bucket_on_first_use() -> None:
    client = FakeMinio(bucket_exists=False)

    await BlobStore(client, "bucket").put("k", b"x")

    assert client.has_bucket


async def test_get_of_a_missing_object_is_none() -> None:
    assert await BlobStore(FakeMinio(), "bucket").get("nope") is None


async def test_other_storage_errors_are_raised() -> None:
    class Broken(FakeMinio):
        def get_object(self, _bucket, _key):
            raise s3_error("AccessDenied")

    with pytest.raises(S3Error):
        await BlobStore(Broken(), "bucket").get("k")


async def test_delete_removes_the_object() -> None:
    client = FakeMinio()
    store = BlobStore(client, "bucket")
    await store.put("a", b"x")

    await store.delete("a")

    assert await store.get("a") is None
