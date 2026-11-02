"""Case files read back from the object store, by the rows that name them."""

from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.case_file import CaseFile
from src.core.gemini.errors import CaseFileNotFoundError


async def stored_files(rows: list[CaseFile], blobs: BlobStore) -> dict[str, bytes]:
    """Read the bytes of every file a case version holds; none touches the store."""
    files = {}
    for row in rows:
        data = await blobs.get(row.object_key)
        if data is None:
            raise CaseFileNotFoundError(f"File {row.name} is missing from storage")
        files[row.name] = data
    return files
