import pytest

from tests.blobs import MemoryBlobStore, blobs  # noqa: F401


@pytest.fixture(autouse=True)
def stored_files(blobs: MemoryBlobStore) -> MemoryBlobStore:  # noqa: F811
    return blobs
