import pytest

from scripts.knowledge import KnowledgeError, add_file
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.rag.search import search_knowledge
from tests.blobs import MemoryBlobStore


async def test_a_catalogue_becomes_one_searchable_shared_document(
    session, make_user, tmp_path
) -> None:
    admin = await make_user("admin@example.com", role="admin")
    blobs = MemoryBlobStore()
    documents = RagDocumentRepository(session)
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


async def test_every_shared_copy_of_the_name_is_replaced_and_others_stay(
    session, make_user, make_project, tmp_path
) -> None:
    admin = await make_user("admin@example.com", role="admin")
    project = await make_project(admin)
    blobs = MemoryBlobStore()
    documents = RagDocumentRepository(session)
    for key in ("knowledge/a/cost.md", "knowledge/b/cost.md", "knowledge/c/other.md"):
        await blobs.put(key, b"old")
        name = key.rsplit("/", 1)[1]
        row = await documents.create(None, name, 3, key, admin.id)
        await documents.set_text(row, "old prices")
    await blobs.put("projects/p/rag/x/cost.md", b"mine")
    own = await documents.create(
        project.id, "cost.md", 4, "projects/p/rag/x/cost.md", admin.id
    )
    path = tmp_path / "cost.md"
    path.write_text("# Costs\n\nPump 210 EUR\n")

    added = await add_file(documents, blobs, path, admin.id)

    assert added["replaced"] == 2
    shared = await documents.named(None, "cost.md")
    assert [row.text for row in shared] == ["# Costs\n\nPump 210 EUR\n"]
    assert shared[0].searchable == "ready"
    assert [row.name for row in await documents.newest_by_name(None)] == [
        "cost.md",
        "other.md",
    ]
    assert [row.id for row in await documents.named(project.id, "cost.md")] == [own.id]
    assert sorted(blobs.objects) == sorted(
        [shared[0].object_key, "knowledge/c/other.md", "projects/p/rag/x/cost.md"]
    )
    old = await search_knowledge(documents, "old prices", 8)
    assert [hit["document"] for hit in old] == ["other.md"]
    new = await search_knowledge(documents, "pump", 8)
    assert [hit["document"] for hit in new] == ["cost.md"]


async def test_a_file_that_cannot_be_read_is_refused(
    session, make_user, tmp_path
) -> None:
    admin = await make_user("admin@example.com", role="admin")
    path = tmp_path / "picture.png"
    path.write_bytes(b"png")
    with pytest.raises(KnowledgeError):
        await add_file(
            RagDocumentRepository(session), MemoryBlobStore(), path, admin.id
        )
