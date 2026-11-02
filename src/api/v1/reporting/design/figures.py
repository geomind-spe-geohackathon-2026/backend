import base64
from html import escape
from typing import Any

WIDTH = 760
FONT = "font-family='Vazirmatn' fill='#17212b'"
MUTED = "font-family='Vazirmatn' fill='#5b6977'"
GRID = "#d3dae1"
SOURCE_COLORS = {"geothermal": "#2f7d4a", "backup": "#a46700", "short": "#b3362c"}
STREAM_COLORS = {"gas": "#7b8794"}
UTILITY_STREAMS = ("electricity", "air", "heat")
DEFAULT_STREAM = "#d0542b"
MONTHS = "JFMAMJJASOND"
TILE_COLUMNS = 4
TILE_WIDTH = WIDTH / TILE_COLUMNS
TILE_HEIGHT = 58
BOX_HEIGHT = 30
ROW_GAP = 12
COLUMN_GAP = 16
LABEL_CHARACTERS = 13


def image_line(svg: str, label: str) -> str:
    """Return a Markdown image holding the SVG, for the preview and the PDF alike."""
    encoded = base64.b64encode(svg.encode()).decode()
    return f"![{label}](data:image/svg+xml;base64,{encoded})"


def frame(height: float, body: str) -> str:
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {WIDTH} {height:.0f}' "
        f"width='{WIDTH}' height='{height:.0f}'>"
        f"<rect width='{WIDTH}' height='{height:.0f}' fill='#ffffff'/>{body}</svg>"
    )


def kpi_tiles(tiles: list[tuple[str, str]]) -> str:
    """Draw the key figures as tiles, four to a row."""
    parts = []
    for index, (title, value) in enumerate(tiles):
        x = (index % TILE_COLUMNS) * TILE_WIDTH + 2
        y = (index // TILE_COLUMNS) * (TILE_HEIGHT + 4) + 2
        parts.append(
            f"<rect x='{x:.0f}' y='{y}' width='{TILE_WIDTH - 4:.0f}' "
            f"height='{TILE_HEIGHT}' rx='6' fill='#ffffff' stroke='{GRID}'/>"
            f"<text x='{x + 10:.0f}' y='{y + 20}' font-size='12' {MUTED}>"
            f"{escape(title)}</text>"
            f"<text x='{x + 10:.0f}' y='{y + 44}' font-size='19' {FONT}>"
            f"{escape(value)}</text>"
        )
    rows = (len(tiles) + TILE_COLUMNS - 1) // TILE_COLUMNS
    return frame(rows * (TILE_HEIGHT + 4) + 2, "".join(parts))


def day_strips(coverage: dict[str, list[dict[str, Any]]]) -> str:
    """Draw one cell per day and service, coloured by the source that covered it."""
    left, row, parts = 70, 24, []
    services = [item for item in coverage.items() if item[1]]
    for index, (service, days) in enumerate(services):
        y = index * (row + 8) + 4
        cell = (WIDTH - left - 8) / len(days)
        parts.append(
            f"<text x='4' y='{y + 16}' font-size='12' {FONT}>"
            f"{escape(service.capitalize())}</text>"
        )
        parts += [
            f"<rect x='{left + at * cell:.2f}' y='{y}' width='{cell + 0.3:.2f}' "
            f"height='{row}' fill='{SOURCE_COLORS[day['source']]}'/>"
            for at, day in enumerate(days)
        ]
    bottom = len(services) * (row + 8) + 18
    x = left
    for source, color in SOURCE_COLORS.items():
        parts.append(
            f"<rect x='{x}' y='{bottom - 11}' width='10' height='10' fill='{color}'/>"
            f"<text x='{x + 14}' y='{bottom - 2}' font-size='11' {MUTED}>"
            f"{source.capitalize()}</text>"
        )
        x += 92
    return frame(bottom + 4, "".join(parts))


def supply_chart(title: str, days: list[dict[str, Any]]) -> str:
    """Draw demand as a line over the stacked energy of geothermal and backup."""
    height, left, top, bottom = 170, 46, 22, 20
    plot_width, plot_height = WIDTH - left - 8, height - top - bottom
    demand = [day["demand"]["value"] for day in days]
    peak = max(demand) or 1
    unit = days[0]["demand"]["unit"]
    scale_x = plot_width / max(len(days) - 1, 1)

    def point(at: int, value: float) -> str:
        return f"{left + at * scale_x:.1f},{top + (1 - value / peak) * plot_height:.1f}"

    geothermal = [day["geothermal"]["value"] for day in days]
    supplied = [
        low + day["backup"]["value"] for low, day in zip(geothermal, days, strict=True)
    ]
    floor = [point(0, 0), point(len(days) - 1, 0)]

    def area(values: list[float], base: list[str], color: str) -> str:
        line = [point(at, value) for at, value in enumerate(values)]
        return f"<polygon points='{' '.join(line + base)}' fill='{color}'/>"

    upper = [point(at, value) for at, value in enumerate(geothermal)][::-1]
    labels = "".join(
        f"<text x='{left + plot_width * at / 12:.0f}' y='{height - 5}' font-size='11' "
        f"{MUTED}>{letter}</text>"
        for at, letter in enumerate(MONTHS)
    )
    body = (
        f"<text x='{left}' y='14' font-size='12' {FONT}>{escape(title)}, "
        f"peak {peak:,.0f} {escape(unit)} a day</text>"
        f"<line x1='{left}' x2='{WIDTH - 8}' y1='{top + plot_height}' "
        f"y2='{top + plot_height}' stroke='{GRID}'/>"
        + area(geothermal, floor[::-1], SOURCE_COLORS["geothermal"])
        + area(supplied, upper, SOURCE_COLORS["backup"])
        + "<polyline points='"
        + " ".join(point(at, value) for at, value in enumerate(demand))
        + "' fill='none' stroke='#17212b' stroke-width='1.2'/>"
        + labels
    )
    return frame(height, body)


def ranks_of(modules: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Place each module one column after the modules that feed it; loops are cut."""
    rank = dict.fromkeys(modules, 0)
    for _ in modules:
        moved = False
        for source, target in edges:
            if source in rank and target in rank and rank[target] <= rank[source]:
                if rank[source] + 1 < len(modules) // 2 + 2:
                    rank[target] = rank[source] + 1
                    moved = True
        if not moved:
            break
    used = sorted(set(rank.values()))
    return {name: used.index(value) for name, value in rank.items()}


def label_lines(name: str) -> tuple[str, str]:
    """Split a module id over two lines at a separator near the middle."""
    if len(name) <= LABEL_CHARACTERS:
        return name, ""
    cut = max(
        name.rfind("_", 0, LABEL_CHARACTERS), name.rfind(".", 0, LABEL_CHARACTERS)
    )
    at = cut + 1 if cut > 0 else LABEL_CHARACTERS
    return name[:at], name[at:][:LABEL_CHARACTERS]


def flowsheet(structure: dict[str, list[dict[str, Any]]]) -> str:
    """Draw the plant left to right: modules by depth, connections by stream."""
    names = [item["id"] for item in structure["modules"]]
    links = [
        (
            item["source"].rpartition(".")[0],
            item["target"].rpartition(".")[0],
            item.get("kind") or item.get("stream") or "",
        )
        for item in structure["connections"]
    ]
    feeds = [
        (source, target)
        for source, target, kind in links
        if kind not in UTILITY_STREAMS
    ]
    rank = ranks_of(names, feeds)
    columns = max(rank.values(), default=0) + 1
    box = (WIDTH - 8 - COLUMN_GAP * (columns - 1)) / columns
    rows: dict[int, int] = {}
    place = {}
    for name in names:
        row = rows.get(rank[name], 0)
        rows[rank[name]] = row + 1
        place[name] = (
            4 + rank[name] * (box + COLUMN_GAP),
            4 + row * (BOX_HEIGHT + ROW_GAP),
        )
    height = max(rows.values(), default=1) * (BOX_HEIGHT + ROW_GAP) + 8
    lines = []
    for source, target, kind in links:
        if source in place and target in place and kind not in UTILITY_STREAMS:
            x1, y1 = place[source]
            x2, y2 = place[target]
            color = STREAM_COLORS.get(kind, DEFAULT_STREAM)
            lines.append(
                f"<line x1='{x1 + box:.1f}' y1='{y1 + BOX_HEIGHT / 2:.1f}' "
                f"x2='{x2:.1f}' y2='{y2 + BOX_HEIGHT / 2:.1f}' "
                f"stroke='{color}' stroke-width='0.8'/>"
            )
    boxes = []
    for name, (x, y) in place.items():
        first, second = label_lines(name)
        boxes.append(
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{box:.1f}' height='{BOX_HEIGHT}' "
            f"rx='4' fill='#ffffff' stroke='#5b6977'/>"
            f"<text x='{x + 3:.1f}' y='{y + 12:.1f}' font-size='8.5' {FONT}>"
            f"{escape(first)}</text>"
            f"<text x='{x + 3:.1f}' y='{y + 23:.1f}' font-size='8.5' {FONT}>"
            f"{escape(second)}</text>"
        )
    return frame(height, "".join(lines + boxes))
