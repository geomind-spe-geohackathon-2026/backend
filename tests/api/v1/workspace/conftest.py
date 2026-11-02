import pytest

from tests.blobs import MemoryBlobStore, blobs  # noqa: F401


@pytest.fixture(autouse=True)
def use_memory_blobs(blobs: MemoryBlobStore) -> None:  # noqa: F811
    return None
