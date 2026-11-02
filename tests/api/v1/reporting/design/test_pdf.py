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
