from pathlib import PurePosixPath

TEXT_SUFFIXES = frozenset(
    {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".log"}
)


def extract_text(name: str, data: bytes) -> str | None:
    """Return the text of a file, or ``None`` when its format cannot be read.

    Only plain-text formats are read; a file that is not valid UTF-8 text, or that
    holds a NUL character (which a text column refuses), has no text.
    """
    if PurePosixPath(name).suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return None if "\x00" in text else text
