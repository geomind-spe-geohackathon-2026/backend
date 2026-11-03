import re
from dataclasses import dataclass

CHUNK_CHARACTERS = 1500
PAGE_LINE = re.compile(r"^\[page (\d+)\]$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Chunk:
    """A passage of a document, with the page it is on when the document has pages."""

    page: int | None
    text: str


def pages_of(text: str) -> list[tuple[int | None, str]]:
    """Split a text at its ``[page n]`` lines; a text without them is one part."""
    marks = list(PAGE_LINE.finditer(text))
    if not marks:
        return [(None, text)]
    parts = []
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        parts.append((int(mark.group(1)), text[mark.end() : end].strip()))
    return parts


def chunks_of(text: str) -> list[Chunk]:
    """Cut a text into passages of about ``CHUNK_CHARACTERS``, by paragraph."""
    chunks = []
    for page, part in pages_of(text):
        current = ""
        for paragraph in re.split(r"\n\s*\n", part):
            if current and len(current) + len(paragraph) > CHUNK_CHARACTERS:
                chunks.append(Chunk(page, current.strip()))
                current = ""
            current = f"{current}\n\n{paragraph}" if current else paragraph
            while len(current) > CHUNK_CHARACTERS:
                chunks.append(Chunk(page, current[:CHUNK_CHARACTERS].strip()))
                current = current[CHUNK_CHARACTERS:]
        if current.strip():
            chunks.append(Chunk(page, current.strip()))
    return chunks
