from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.rag.extract import extract_text, is_supported
from src.core.rag.search import search_documents


def test_text_files_are_read() -> None:
    assert extract_text("notes.MD", b"Porosity 0.2") == "Porosity 0.2"


def pdf_with(text: str) -> bytes:
    from fpdf import FPDF

    document = FPDF()
    document.add_page()
    document.set_font("Helvetica", size=12)
    document.cell(text=text)
    return bytes(document.output())


def test_the_text_of_a_pdf_is_read() -> None:
    assert "Porosity 0.2" in (
        extract_text("report.pdf", pdf_with("Porosity 0.2")) or ""
    )


def test_a_broken_pdf_has_no_text() -> None:
    assert extract_text("scan.pdf", b"%PDF") is None


def test_other_formats_have_no_text() -> None:
    assert extract_text("tool.exe", b"MZ") is None


def test_binary_content_has_no_text() -> None:
    assert extract_text("a.txt", b"\xff\xfe") is None
    assert extract_text("a.txt", b"a\x00b") is None


async def add_ready(session, project, owner, name: str, text: str) -> None:
    repository = RagDocumentRepository(session)
    document = await repository.create(project.id, name, len(text), name, owner.id)
    await repository.set_text(document, text)


async def test_search_ranks_by_occurrences(session, make_user, make_project) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await add_ready(session, project, owner, "one.txt", "Brine has a high salinity")
    await add_ready(session, project, owner, "two.txt", "salinity, salinity: Salinity")
    await add_ready(session, project, owner, "three.txt", "nothing here")

    hits = await search_documents(
        RagDocumentRepository(session), project.id, "SALINITY", 5
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
    repository = RagDocumentRepository(session)

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
        await search_documents(RagDocumentRepository(session), second.id, "heat", 5)
        == []
    )


def test_a_file_type_is_supported_when_it_can_be_read() -> None:
    assert is_supported("a.PDF")
    assert is_supported("a.csv")
    assert not is_supported("bad.exe")
