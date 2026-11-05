import base64
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import WrapMode

from src.api.v1.reporting.design import figures
from src.core import fonts

HEADING_SIZES = {1: 22, 2: 17, 3: 13.5, 4: 11.5}
HEADING_BEFORE = {1: 0, 2: 0, 3: 7, 4: 5}
"""Space [mm] above a heading: larger than below it, so a heading sits with its text."""
HEADING_AFTER = 2.5
TEXT_SIZE = 10.5
CAPTION_SIZE = 8.5
CAPTION_GREY = 105
CAPTION_SLANT = 12
"""The slant [degree] that writes a caption in italics: the font has no italic face."""
CODE_SIZE = 7
LINE_HEIGHT = 5.4
SIDE_MARGIN = 28
"""Left and right margins [mm] of a portrait page: lines of about 75 characters (QA-313)."""
TOP_MARGIN = 20
TOP_SECTION = 2
"""The heading level of a top-level section, which starts a new page."""
FENCE = "```"
IMAGE = "!["
WIDE_IMAGE = "![Detailed flowsheet]"
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


def is_caption(line: str) -> bool:
    found = line.strip()
    return (
        len(found) > 2
        and found.startswith("*")
        and found.endswith("*")
        and (not found.startswith("**"))
    )


def block_kind(line: str) -> str:
    if line.lstrip().startswith("<"):
        return "html"
    if is_caption(line):
        return "caption"
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
    if kind in ("heading", "bullet", "image", "html", "caption"):
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


def at_page_top(pdf: FPDF) -> bool:
    return pdf.get_y() <= pdf.t_margin + 1


def write_heading(pdf: FPDF, line: str, after_title: bool = False) -> None:
    """Write a heading: larger and bolder by level; a top-level section starts a page.

    The first section stays on the page of the report's title.
    """
    level = len(line) - len(line.lstrip("#"))
    if level == TOP_SECTION and not at_page_top(pdf) and not after_title:
        pdf.add_page()
    elif not at_page_top(pdf):
        pdf.ln(HEADING_BEFORE.get(level, 4))
    size = HEADING_SIZES.get(level, TEXT_SIZE)
    pdf.set_font(FONT, "B", size)
    pdf.multi_cell(0, size * 0.5, line.lstrip("# "), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(HEADING_AFTER + (2 if level <= TOP_SECTION else 0))


def write_caption(pdf: FPDF, line: str) -> None:
    """Write a caption under its figure or table: small, grey, slanted and centred."""
    pdf.set_font(FONT, size=CAPTION_SIZE)
    pdf.set_text_color(CAPTION_GREY)
    words = line.strip().strip("*")
    width = pdf.get_string_width(words)
    x = pdf.l_margin + max((pdf.epw - width) / 2, 0)
    y = pdf.get_y()
    with pdf.skew(ax=CAPTION_SLANT, x=x, y=y + 4):
        pdf.multi_cell(0, 4.2, words, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0)
    pdf.ln(2.5)


def write_image(pdf: FPDF, line: str) -> None:
    """Draw an SVG image line across the page; a wide one has a landscape page."""
    encoded = line.rpartition(",")[2].rstrip(")")
    svg = base64.b64decode(encoded).decode().replace(figures.SANS, FONT)
    wide = line.startswith(WIDE_IMAGE)
    if wide:
        pdf.add_page(orientation="L")
    pdf.image(BytesIO(svg.encode()), w=pdf.epw)
    pdf.ln(2)


def back_to_portrait(pdf: FPDF) -> None:
    """Start a portrait page for what follows a landscape figure."""
    if pdf.w > pdf.h:
        pdf.add_page(orientation="P")


def keep_with_next(pdf: FPDF, kind: str) -> None:
    """Start a page for a heading too close to the bottom to have its text under it."""
    if kind == "heading" and pdf.get_y() > pdf.page_break_trigger - 30:
        pdf.add_page()


def alignments(lines: list[str]) -> tuple[str, ...] | str:
    """Return each column's alignment from the Markdown separator: ``---:`` is right."""
    found = next((line for line in lines if is_separator(line)), None)
    if found is None:
        return "LEFT"
    return tuple(
        "RIGHT" if cell.strip().endswith(":") else "LEFT" for cell in cells_of(found)
    )


def write_table(pdf: FPDF, lines: list[str]) -> None:
    pdf.ln(1.5)
    pdf.set_font(FONT, size=9)
    with pdf.table(text_align=alignments(lines)) as table:
        for line in lines:
            if is_separator(line):
                continue
            row = table.row()
            for cell in cells_of(line):
                row.cell(cell)
    pdf.ln(1.5)


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
    pdf.multi_cell(0, LINE_HEIGHT, text, align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2.5)


def to_pdf(markdown: str) -> bytes:
    """Draw Markdown (headings, tables, code, bullets, paragraphs) as a PDF."""
    pdf = FPDF()
    pdf.set_margins(SIDE_MARGIN, TOP_MARGIN, SIDE_MARGIN)
    pdf.add_font(FONT, "", str(FONT_DIR / "Vazirmatn-Regular.ttf"))
    pdf.add_font(FONT, "B", str(FONT_DIR / "Vazirmatn-Bold.ttf"))
    pdf.set_text_shaping(True)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    previous = None
    for block in blocks_of(markdown):
        if block.kind == "html":
            continue
        after_title = previous is not None and previous.lines[0].startswith("# ")
        previous = block
        back_to_portrait(pdf)
        keep_with_next(pdf, block.kind)
        if block.kind == "caption":
            write_caption(pdf, block.lines[0])
        elif block.kind == "image":
            write_image(pdf, block.lines[0])
        elif block.kind == "heading":
            write_heading(pdf, block.lines[0], after_title)
        elif block.kind == "table":
            write_table(pdf, block.lines)
        elif block.kind == "code":
            write_code(pdf, block.lines)
        else:
            write_text(pdf, block)
    return bytes(pdf.output())
