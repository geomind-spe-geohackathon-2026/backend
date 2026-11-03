import pytest

from src.core.clients.postgres.repositories.document import DocumentRepository
from src.scripts.knowledge import KnowledgeError, add_file
from tests.blobs import MemoryBlobStore


async def test_a_catalogue_becomes_one_searchable_shared_document(
    session, make_user, tmp_path
) -> None:
    admin = await make_user("admin@example.com", role="admin")
    blobs = MemoryBlobStore()
    documents = DocumentRepository(session)
    path = tmp_path / "catalogue.csv"
    path.write_text("id,item,value\npump,Pump cost,200\n")

    first = await add_file(documents, blobs, path, admin.id)
    path.write_text("id,item,value\npump,Pump cost,210\n")
    second = await add_file(documents, blobs, path, admin.id)

    shared = await documents.newest_by_name(None)
    assert (first["replaced"], second["replaced"]) == (0, 1)
    assert [row.name for row in shared] == ["catalogue.csv"]
    assert shared[0].searchable == "ready" and "210" in shared[0].text
    assert list(blobs.objects.values()) == [path.read_bytes()]


async def test_a_file_that_cannot_be_read_is_refused(
    session, make_user, tmp_path
) -> None:
    admin = await make_user("admin@example.com", role="admin")
    path = tmp_path / "picture.png"
    path.write_bytes(b"png")
    with pytest.raises(KnowledgeError):
        await add_file(DocumentRepository(session), MemoryBlobStore(), path, admin.id)
