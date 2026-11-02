import re
import zlib

from src.api.v1.reporting.design import pdf

MARKDOWN = """# Title

## Costs

| Figure | Value |
| --- | --- |
| Capex | missing (no value) |

Text line one
text line two

- item

```
Plant: X
```
"""


def test_markdown_splits_into_blocks() -> None:
    kinds = [block.kind for block in pdf.blocks_of(MARKDOWN)]

    assert kinds == ["heading", "heading", "table", "paragraph", "bullet", "code"]


def test_markdown_becomes_a_pdf() -> None:
    document = pdf.to_pdf(MARKDOWN + "\nSymbols outside Latin-1: ≥ €")

    assert document.startswith(b"%PDF")


def printed_codepoints(document: bytes) -> set[int]:
    codepoints: set[int] = set()
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", document, re.DOTALL):
        try:
            stream = zlib.decompress(stream)
        except zlib.error:
            pass
        text = stream.decode("latin-1")
        for match in re.finditer(r"<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]{4})>", text):
            codepoints.add(int(match.group(2), 16))
    return codepoints


def test_persian_text_is_embedded_without_question_marks() -> None:
    name = "پروژه زمین گرمایی"

    document = pdf.to_pdf(f"# {name}\n\nSite: {name}")

    codepoints = printed_codepoints(document)
    assert {ord(character) for character in name if character != " "} <= codepoints
    assert ord("?") not in codepoints
