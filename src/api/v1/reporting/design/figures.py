import base64
import math
from html import escape
from typing import Any

WIDTH = 760
SANS = "Helvetica, Arial, sans-serif"
FONT = f"font-family='{SANS}' fill='#17212b'"
MUTED = f"font-family='{SANS}' fill='#5b6977'"
GRID = "#d3dae1"
ELECTRICITY_COLOR = "#3b6ea8"
ELECTRICITY_WORD = "Heat-pump electricity"
"""The heat pumps' compressor work, apart from the brine heat since gemini 0.6.22 (QA-270)."""
KEY_GAP = 24
KEY_CHAR = 5.6
KEY_AFTER_TITLE = 200
"""Where the legend of a chart may start at the earliest, right of its title [px]."""
SOURCE_COLORS = {"geothermal": "#2f7d4a", "backup": "#a46700", "short": "#b3362c"}
MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
TILE_COLUMNS = 4
TILE_WIDTH = WIDTH / TILE_COLUMNS
TILE_HEIGHT = 58


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


def source_word(service: str, source: str) -> str:
    """Name a source: gemini has no backup for cooling, so all of it is the plant."""
    if source == "geothermal" and service == "cooling":
        return "Plant"
    return source.capitalize()


NO_DEMAND_COLOR = "#d5d9de"
"""A day whose consumers asked for nothing: neither the plant nor its other units (QA-322)."""
FALLBACK_LABELS = {"heating": ("Geothermal", "Backup"), "cooling": ("Plant", None)}
"""What a coverage stored before gemini 0.6.31 calls its main and other supply."""


def labels_of(service: str, days: list[dict[str, Any]]) -> tuple[str, str | None]:
    """Return ``(main, other)``: gemini's names of what covered a service's days (QA-322)."""
    found = next((day.get("labels") for day in days if day.get("labels")), None)
    if isinstance(found, dict) and found.get("main"):
        return found["main"], found.get("other")
    return FALLBACK_LABELS.get(service, ("Plant", None))


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
            f"height='{row}' fill='{day_color(day)}'/>"
            for at, day in enumerate(days)
        ]
    bottom = len(services) * (row + 8) + 18
    x = left
    words = {"geothermal": "Main supply", "backup": "Other supply"}
    keys = list(SOURCE_COLORS.items())
    if any(day.get("no_demand") for _, days in services for day in days):
        keys.append(("no demand", NO_DEMAND_COLOR))
    for source, color in keys:
        word = words.get(source, source.capitalize())
        parts.append(
            f"<rect x='{x}' y='{bottom - 11}' width='10' height='10' fill='{color}'/>"
            f"<text x='{x + 14}' y='{bottom - 2}' font-size='11' {MUTED}>"
            f"{word}</text>"
        )
        x += 20 + len(word) * 6
    return frame(bottom + 4, "".join(parts))


def day_color(day: dict[str, Any]) -> str:
    return NO_DEMAND_COLOR if day.get("no_demand") else SOURCE_COLORS[day["source"]]


def supply_chart(
    title: str, days: list[dict[str, Any]], labels: tuple[str, str]
) -> str:
    """Draw mean power per day: demand as a line over the stacked supply."""
    height, left, top, bottom = 190, 52, 40, 22
    plot_width, plot_height = WIDTH - left - 12, height - top - bottom
    hours = 24
    demand = [day["demand"]["value"] / hours for day in days]
    ticks = nice_ticks(max(demand) or 1)
    peak = ticks[-1]
    scale_x = plot_width / max(len(days) - 1, 1)

    def point(at: int, value: float) -> str:
        return f"{left + at * scale_x:.1f},{top + (1 - value / peak) * plot_height:.1f}"

    def height_of(value: float) -> float:
        return top + (1 - value / peak) * plot_height

    first = [day["geothermal"]["value"] / hours for day in days]
    split = all("electricity" in day for day in days)
    middle = [
        low + (day["electricity"]["value"] / hours if split else 0.0)
        for low, day in zip(first, days, strict=True)
    ]
    stacked = [
        low + day["backup"]["value"] / hours
        for low, day in zip(middle, days, strict=True)
    ]
    floor = [point(0, 0), point(len(days) - 1, 0)]

    def area(values: list[float], base: list[str], color: str) -> str:
        line = [point(at, value) for at, value in enumerate(values)]
        return f"<polygon points='{' '.join(line + base)}' fill='{color}'/>"

    upper = [point(at, value) for at, value in enumerate(first)][::-1]
    above = [point(at, value) for at, value in enumerate(middle)][::-1]
    grid = "".join(
        f"<line x1='{left}' x2='{WIDTH - 12}' y1='{height_of(tick):.1f}' "
        f"y2='{height_of(tick):.1f}' stroke='{GRID}'/>"
        f"<text x='{left - 6}' y='{height_of(tick) + 4:.1f}' font-size='11' "
        f"text-anchor='end' {MUTED}>{tick:g}</text>"
        for tick in ticks
    )
    months = "".join(
        f"<text x='{left + plot_width * at / 12:.0f}' y='{height - 6}' font-size='11' "
        f"{MUTED}>{name}</text>"
        for at, name in enumerate(MONTHS)
    )
    key = [(labels[0], SOURCE_COLORS["geothermal"])]
    if split and any(day["electricity"]["value"] for day in days):
        key.append((ELECTRICITY_WORD, ELECTRICITY_COLOR))
    key += [(labels[1], SOURCE_COLORS["backup"]), ("Demand", "#17212b")]
    widths = [KEY_GAP + len(name) * KEY_CHAR for name, _ in key]
    x = max(left + KEY_AFTER_TITLE, WIDTH - 12 - sum(widths))
    places = []
    for width in widths:
        places.append(x)
        x += width
    legend = "".join(
        f"<rect x='{at:.0f}' y='5' width='10' height='10' "
        f"fill='{color}'/><text x='{at + 14:.0f}' y='14' "
        f"font-size='11' {MUTED}>{escape(name)}</text>"
        for at, (name, color) in zip(places, key, strict=True)
    )
    body = (
        f"<text x='{left}' y='14' font-size='13' {FONT}>{escape(title)}</text>"
        f"<text x='8' y='30' font-size='11' {MUTED}>MW, daily mean</text>"
        + legend
        + grid
        + area(first, floor[::-1], SOURCE_COLORS["geothermal"])
        + area(middle, upper, ELECTRICITY_COLOR)
        + area(stacked, above, SOURCE_COLORS["backup"])
        + "<polyline points='"
        + " ".join(point(at, value) for at, value in enumerate(demand))
        + "' fill='none' stroke='#17212b' stroke-width='1.2'/>"
        + months
    )
    return frame(height, body)


def nice_ticks(peak: float) -> list[float]:
    """Return round values from zero to just above the peak."""
    step = 10 ** math.floor(math.log10(peak))
    if peak / step < 2:
        step /= 2
    count = math.ceil(peak / step)
    return [index * step for index in range(count + 1)]
