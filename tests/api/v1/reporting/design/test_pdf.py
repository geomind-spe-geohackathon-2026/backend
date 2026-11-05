import base64
import re
import zlib
from pathlib import Path

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

PAGE = re.compile(rb"/Type\s*/Page(?![a-z])")


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
    name = (
        "\u067e\u0631\u0648\u0698\u0647 "
        "\u0632\u0645\u06cc\u0646 "
        "\u06af\u0631\u0645\u0627\u06cc\u06cc"
    )

    document = pdf.to_pdf(f"# {name}\n\nSite: {name}")

    codepoints = printed_codepoints(document)
    assert {ord(character) for character in name if character != " "} <= codepoints
    assert ord("?") not in codepoints


def test_an_svg_image_line_is_drawn_into_the_pdf() -> None:
    svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'></svg>"
    encoded = base64.b64encode(svg.encode()).decode()

    data = pdf.to_pdf(f"![Figure](data:image/svg+xml;base64,{encoded})\n")

    assert data.startswith(b"%PDF")


def test_a_wide_image_has_its_own_landscape_page_and_no_blank_one() -> None:
    svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 10'></svg>"
    encoded = base64.b64encode(svg.encode()).decode()
    line = f"![Detailed flowsheet](data:image/svg+xml;base64,{encoded})"

    last = pdf.to_pdf(f"Text\n\n{line}\n")
    followed = pdf.to_pdf(f"Text\n\n{line}\n\nMore text\n")

    assert len(PAGE.findall(last)) == 2
    assert len(PAGE.findall(followed)) == 3


def test_each_top_level_section_starts_a_page_the_first_with_the_title() -> None:
    markdown = "\n\n".join(
        [
            "# Report",
            "## 1 Summary",
            "Text.",
            '<div style="page-break-before: always"></div>',
            "## 2 Case",
            "| Value | Amount |\n| --- | ---: |\n| Depth | 2,500\u2009m |",
            "*Table 2.1 - Values*",
            "### 2.1 Demand",
            "Text.",
            "## 3 Plant",
            "Text.",
        ]
    )

    kinds = [block.kind for block in pdf.blocks_of(markdown)]

    assert "html" in kinds
    assert "caption" in kinds
    assert pdf.alignments(["| a | b |", "| --- | ---: |"]) == ("LEFT", "RIGHT")
    assert len(PAGE.findall(pdf.to_pdf(markdown))) == 3


def test_a_compact_report_is_drawn() -> None:
    markdown = (
        Path(__file__).parents[3 + 1] / "fixtures" / "report_compact.md"
    ).read_text()

    assert pdf.to_pdf(markdown).startswith(b"%PDF")
