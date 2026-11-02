from src.core.clients.postgres.repositories.document import DocumentRepository
from src.core.documents.extract import extract_text
from src.core.documents.search import search_documents


def test_text_files_are_read() -> None:
    assert extract_text("notes.MD", b"Porosity 0.2") == "Porosity 0.2"


def test_other_formats_have_no_text() -> None:
    assert extract_text("scan.pdf", b"%PDF") is None


def test_binary_content_has_no_text() -> None:
    assert extract_text("a.txt", b"\xff\xfe") is None
    assert extract_text("a.txt", b"a\x00b") is None


async def add_ready(session, project, owner, name: str, text: str) -> None:
    repository = DocumentRepository(session)
    document = await repository.create(project.id, name, len(text), name, owner.id)
    await repository.set_text(document, text)


async def test_search_ranks_by_occurrences(session, make_user, make_project) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await add_ready(session, project, owner, "one.txt", "Brine has a high salinity")
    await add_ready(session, project, owner, "two.txt", "salinity, salinity: Salinity")
    await add_ready(session, project, owner, "three.txt", "nothing here")

    hits = await search_documents(
        DocumentRepository(session), project.id, "SALINITY", 5
    )

    assert [hit["title"] for hit in hits] == ["two.txt", "one.txt"]
    assert hits[0]["score"] == 3
    assert "salinity" in hits[1]["text"]


async def test_search_needs_every_word_and_respects_the_limit(
    session,
    make_user,
    make_project,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await add_ready(session, project, owner, "a.txt", "heat demand and supply")
    await add_ready(session, project, owner, "b.txt", "heat only")
    repository = DocumentRepository(session)

    both = await search_documents(repository, project.id, "heat supply", 5)
    one = await search_documents(repository, project.id, "heat", 1)

    assert [hit["title"] for hit in both] == ["a.txt"]
    assert len(one) == 1
    assert await search_documents(repository, project.id, "  ", 5) == []


async def test_search_stays_inside_the_project(
    session,
    make_user,
    make_project,
) -> None:
    owner = await make_user()
    first = await make_project(owner)
    second = await make_project(owner)
    await add_ready(session, first, owner, "a.txt", "heat")

    assert (
        await search_documents(DocumentRepository(session), second.id, "heat", 5) == []
    )
