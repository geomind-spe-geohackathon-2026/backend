from collections.abc import Iterator
from dataclasses import dataclass

from fpdf import FPDF
from fpdf.enums import WrapMode

HEADING_SIZES = {1: 18, 2: 14}
TEXT_SIZE = 10
CODE_SIZE = 7
LINE_HEIGHT = 5
FENCE = "```"


@dataclass(frozen=True, slots=True)
class Block:
    kind: str
    lines: list[str]


def printable(text: str) -> str:
    """Make text fit the built-in PDF font, which holds Latin-1 only."""
    return text.encode("latin-1", "replace").decode("latin-1")


def cells_of(line: str) -> list[str]:
    return [
        cell.strip().replace("\\|", "|")
        for cell in line.strip().strip("|").split(" | ")
    ]


def is_separator(line: str) -> bool:
    return set(line.replace("|", "").replace(" ", "")) <= {"-", ":"}


def blocks_of(markdown: str) -> Iterator[Block]:
    """Split Markdown into headings, tables, code, bullets and paragraphs."""
    lines = markdown.splitlines()
    position = 0
    while position < len(lines):
        line = lines[position]
        if not line.strip():
            position += 1
            continue
        kind = block_kind(line)
        end = block_end(lines, position, kind)
        yield Block(kind, lines[position + (kind == "code") : end])
        position = end + (kind == "code")


def block_kind(line: str) -> str:
    if line.startswith(FENCE):
        return "code"
    if line.startswith("#"):
        return "heading"
    if line.startswith("|"):
        return "table"
    return "bullet" if line.startswith("- ") else "paragraph"


def block_end(lines: list[str], start: int, kind: str) -> int:
    if kind in ("heading", "bullet"):
        return start + 1
    end = start + 1
    while end < len(lines) and continues(lines[end], kind):
        end += 1
    return end


def continues(line: str, kind: str) -> bool:
    if kind == "code":
        return not line.startswith(FENCE)
    if kind == "table":
        return line.startswith("|")
    return bool(line.strip()) and block_kind(line) == "paragraph"


def write_heading(pdf: FPDF, line: str) -> None:
    level = len(line) - len(line.lstrip("#"))
    pdf.set_font("Helvetica", "B", HEADING_SIZES.get(level, 12))
    pdf.multi_cell(0, 8, printable(line.lstrip("# ")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def write_table(pdf: FPDF, lines: list[str]) -> None:
    pdf.set_font("Helvetica", size=9)
    with pdf.table(text_align="LEFT") as table:
        for line in lines:
            if is_separator(line):
                continue
            row = table.row()
            for cell in cells_of(line):
                row.cell(printable(cell))
    pdf.ln(2)


def write_code(pdf: FPDF, lines: list[str]) -> None:
    pdf.set_font("Courier", size=CODE_SIZE)
    for line in lines:
        pdf.multi_cell(
            0,
            3.5,
            printable(line) or " ",
            new_x="LMARGIN",
            new_y="NEXT",
            wrapmode=WrapMode.CHAR,
        )
    pdf.ln(2)


def write_text(pdf: FPDF, block: Block) -> None:
    pdf.set_font("Helvetica", size=TEXT_SIZE)
    text = printable(" ".join(line.strip() for line in block.lines))
    pdf.multi_cell(0, LINE_HEIGHT, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def to_pdf(markdown: str) -> bytes:
    """Draw Markdown (headings, tables, code, bullets, paragraphs) as a PDF."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    for block in blocks_of(markdown):
        if block.kind == "heading":
            write_heading(pdf, block.lines[0])
        elif block.kind == "table":
            write_table(pdf, block.lines)
        elif block.kind == "code":
            write_code(pdf, block.lines)
        else:
            write_text(pdf, block)
    return bytes(pdf.output())
