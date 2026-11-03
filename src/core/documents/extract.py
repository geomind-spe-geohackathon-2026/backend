import io
from pathlib import PurePosixPath

from pypdf import PdfReader
from pypdf.errors import PyPdfError

TEXT_SUFFIXES = frozenset(
    {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".log"}
)
PDF_SUFFIX = ".pdf"
PAGE_MARK = "[page {}]"
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | {PDF_SUFFIX}


def is_supported(name: str) -> bool:
    """Tell whether a file of this name is a type whose text can be read."""
    return PurePosixPath(name).suffix.lower() in SUPPORTED_SUFFIXES


def text_of_pdf(data: bytes) -> str | None:
    """Return the text of a PDF, or ``None`` when it is damaged or holds no text.

    Each page starts with a ``[page n]`` line, so a passage found later keeps its page.
    """
    try:
        pages = PdfReader(io.BytesIO(data)).pages
        parts = [
            f"{PAGE_MARK.format(number)}\n{page.extract_text()}"
            for number, page in enumerate(pages, start=1)
        ]
        text = "\n".join(parts).strip()
        if not "".join(page.extract_text() for page in pages).strip():
            return None
    except (PyPdfError, ValueError, KeyError, OSError):
        return None
    return None if not text or "\x00" in text else text


def extract_text(name: str, data: bytes) -> str | None:
    """Return the text of a file, or ``None`` when its format cannot be read.

    Plain-text formats and PDFs are read; a file that is not valid UTF-8 text, a
    damaged or scanned PDF, or text with a NUL character (which a text column
    refuses), has no text.
    """
    suffix = PurePosixPath(name).suffix.lower()
    if suffix == PDF_SUFFIX:
        return text_of_pdf(data)
    if suffix not in TEXT_SUFFIXES:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return None if "\x00" in text else text
