from src.core.documents.chunks import CHUNK_CHARACTERS, chunks_of


def test_a_text_without_pages_is_cut_by_paragraph() -> None:
    text = "\n\n".join(["a" * 900, "b" * 900, "c" * 10])
    chunks = chunks_of(text)
    assert [chunk.page for chunk in chunks] == [None, None]
    assert all(len(chunk.text) <= CHUNK_CHARACTERS for chunk in chunks)


def test_pages_are_kept_and_a_long_paragraph_is_split() -> None:
    text = "[page 1]\nshort\n[page 2]\n" + "x" * (CHUNK_CHARACTERS * 2 + 5)
    chunks = chunks_of(text)
    assert chunks[0].page == 1 and chunks[0].text == "short"
    assert {chunk.page for chunk in chunks[1:]} == {2}
    assert sum(len(chunk.text) for chunk in chunks[1:]) == CHUNK_CHARACTERS * 2 + 5
