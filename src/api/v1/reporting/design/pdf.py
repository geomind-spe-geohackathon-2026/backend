import base64
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import WrapMode

from src.api.v1.reporting.design import figures
from src.core import fonts

HEADING_SIZES = {1: 18, 2: 14}
TEXT_SIZE = 10
CODE_SIZE = 7
LINE_HEIGHT = 5
FENCE = "```"
IMAGE = "!["
WIDE_IMAGE = "![Flowsheet]"
FONT = "Vazirmatn"
FONT_DIR = Path(fonts.__file__).parent


@dataclass(frozen=True, slots=True)
class Block:
    kind: str
    lines: list[str]


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
    if line.startswith(IMAGE):
        return "image"
    if line.startswith(FENCE):
        return "code"
    if line.startswith("#"):
        return "heading"
    if line.startswith("|"):
        return "table"
    return "bullet" if line.startswith("- ") else "paragraph"


def block_end(lines: list[str], start: int, kind: str) -> int:
    if kind in ("heading", "bullet", "image"):
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
    pdf.set_font(FONT, "B", HEADING_SIZES.get(level, 12))
    pdf.multi_cell(0, 8, line.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def write_image(pdf: FPDF, line: str) -> None:
    """Draw an SVG image line across the page; a flowsheet takes a landscape page."""
    encoded = line.rpartition(",")[2].rstrip(")")
    svg = base64.b64decode(encoded).decode().replace(figures.SANS, FONT)
    wide = line.startswith(WIDE_IMAGE)
    if wide:
        pdf.add_page(orientation="L")
    pdf.image(BytesIO(svg.encode()), w=pdf.epw)
    pdf.ln(2)
    if wide:
        pdf.add_page(orientation="P")


def write_table(pdf: FPDF, lines: list[str]) -> None:
    pdf.set_font(FONT, size=9)
    with pdf.table(text_align="LEFT") as table:
        for line in lines:
            if is_separator(line):
                continue
            row = table.row()
            for cell in cells_of(line):
                row.cell(cell)
    pdf.ln(2)


def write_code(pdf: FPDF, lines: list[str]) -> None:
    pdf.set_font(FONT, size=CODE_SIZE)
    for line in lines:
        pdf.multi_cell(
            0,
            3.5,
            line or " ",
            new_x="LMARGIN",
            new_y="NEXT",
            wrapmode=WrapMode.CHAR,
        )
    pdf.ln(2)


def write_text(pdf: FPDF, block: Block) -> None:
    pdf.set_font(FONT, size=TEXT_SIZE)
    text = " ".join(line.strip() for line in block.lines)
    pdf.multi_cell(0, LINE_HEIGHT, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def to_pdf(markdown: str) -> bytes:
    """Draw Markdown (headings, tables, code, bullets, paragraphs) as a PDF."""
    pdf = FPDF()
    pdf.add_font(FONT, "", str(FONT_DIR / "Vazirmatn-Regular.ttf"))
    pdf.add_font(FONT, "B", str(FONT_DIR / "Vazirmatn-Bold.ttf"))
    pdf.set_text_shaping(True)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    for block in blocks_of(markdown):
        if block.kind == "image":
            write_image(pdf, block.lines[0])
        elif block.kind == "heading":
            write_heading(pdf, block.lines[0])
        elif block.kind == "table":
            write_table(pdf, block.lines)
        elif block.kind == "code":
            write_code(pdf, block.lines)
        else:
            write_text(pdf, block)
    return bytes(pdf.output())
