import re
from typing import Any

from src.core.gemini import evaluate as gemini_evaluate

ENERGY_GROUP = "Energy balance"
ECONOMICS_GROUP = "Economics"
EMISSIONS_GROUP = "Emissions"
OTHER_GROUP = "Other figures"
SIGNIFICANT = 4
ENERGY_UNITS = ("MWh", "GWh")
EMISSION_UNITS = ("kt", "t")
THOUSAND = 1000
PERCENT = 100
SHORT_ID = 3
WELLS_GROUP = "Wells"
SURFACE_GROUP = "Surface plant"
OTHER_CAPEX_GROUP = "Other"
CAPEX_GROUPS = (WELLS_GROUP, SURFACE_GROUP, OTHER_CAPEX_GROUP)
CAPEX_KINDS = {
    WELLS_GROUP: ("drilling", "production_pump"),
    OTHER_CAPEX_GROUP: ("pipe", "flare", "gas_makeup"),
}
NOISE = 1e-3
TILE_FIGURES = ("lcts", "capex", "opex", "co2", "heat_delivered", "cold_delivered")


def number_text(value: float) -> str:
    """Write a number with four significant digits and thousands separators."""
    rounded = float(f"{value:.{SIGNIFICANT}g}")
    return f"{rounded:,.0f}" if rounded.is_integer() else f"{rounded:,g}"


def figure_text(item: dict[str, Any]) -> str:
    """Write a figure in a readable unit; a missing one says why."""
    value, unit = item["value"], item["unit"]
    if value is None:
        return gemini_evaluate.amount(item)
    if unit == ENERGY_UNITS[0] and abs(value) >= THOUSAND:
        return f"{number_text(value / THOUSAND)} {ENERGY_UNITS[1]}"
    return f"{number_text(value)} {unit}" if unit != "-" else number_text(value)


def margin_text(margin: float, unit: str) -> str:
    """Write a margin; floating point noise on a bound is no margin at all."""
    shown = 0.0 if abs(margin) < NOISE else margin
    return figure_text({"value": shown, "unit": unit})


def group_of(unit: str) -> str:
    """Return the section a figure belongs to, from its unit."""
    if unit in ENERGY_UNITS:
        return ENERGY_GROUP
    if unit.startswith(("EUR", "MEUR", "kEUR")):
        return ECONOMICS_GROUP
    if unit in EMISSION_UNITS:
        return EMISSIONS_GROUP
    return OTHER_GROUP


def grouped_figures(report: dict[str, Any]) -> dict[str, list[list[str]]]:
    """Return the report's figures as table rows by section."""
    groups: dict[str, list[list[str]]] = {
        ECONOMICS_GROUP: [],
        ENERGY_GROUP: [],
        EMISSIONS_GROUP: [],
        OTHER_GROUP: [],
    }
    for name, item in report.items():
        if gemini_evaluate.is_quantity(item):
            title = item.get("title", gemini_evaluate.title_of(name))
            groups[group_of(item["unit"])].append([title, figure_text(item)])
    return {name: rows for name, rows in groups.items() if rows}


def share_text(coverage: dict[str, Any] | None) -> str | None:
    """Write how much of the heating demand came from the brine, heat pumps and backup.

    Before gemini 0.6.22 a coverage day had no ``electricity``: its ``geothermal`` held the
    heat pumps' compressor work too, so such a share is named so (QA-270).
    """
    shares = heat_shares(coverage)
    if shares is None:
        return None
    if shares["electricity"] is None:
        return (
            f"Geothermal, with any heat-pump electricity, covers "
            f"{shares['geothermal'] * PERCENT:.0f}% of the heating demand."
        )
    parts = [f"geothermal brine heat {shares['geothermal'] * PERCENT:.0f}%"]
    if shares["electricity"] > 0:
        parts.append(f"heat-pump electricity {shares['electricity'] * PERCENT:.0f}%")
    parts.append(f"backup {shares['backup'] * PERCENT:.0f}%")
    return f"Of the heating demand, {', '.join(parts)}."


def module_words(name: str) -> str:
    """Write a module id in words; a short id such as d0 stays as it is."""
    if len(name) <= SHORT_ID:
        return name
    words = name.replace(".", " ").replace("_", " ")
    return words[0].upper() + words[1:]


def spaced(name: str) -> str:
    """Write a class name in words."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return words[:1] + words[1:].lower()


def largest_text(capacities: list[dict[str, Any]]) -> str | None:
    """Name the largest rated units in the unit most of the plant uses."""
    power = [item for item in capacities if item["unit"] == "MW"]
    largest = sorted(power, key=lambda item: item["value"] or 0, reverse=True)[:3]
    if not largest:
        return None
    names = ", ".join(
        f"{module_words(item['title'])} {number_text(item['value'])} MW"
        for item in largest
    )
    return f"The largest rated units are {names}."


def verdict_text(checks: dict[str, int]) -> str:
    """Write the outcome of the checks of a result."""
    total = sum(checks.values())
    if checks["failed"]:
        return f"{checks['failed']} of {total} checks fail."
    return f"All {checks['passed']} assessed checks pass."


def summary_sentences(
    report: dict[str, Any],
    capacities: list[dict[str, Any]],
    coverage: dict[str, Any] | None,
    checks: dict[str, int],
) -> list[str]:
    """Write the few sentences that open a report, from the result alone."""
    lines = []
    energy = [
        f"{figure_text(report[name])} of {word}"
        for name, word in (("heat_delivered", "heat"), ("cold_delivered", "cold"))
        if gemini_evaluate.is_quantity(report.get(name))
        and report[name]["value"] is not None
    ]
    if energy:
        lines.append(f"The design delivers {' and '.join(energy)} a year.")
    cost = report.get("lcts")
    if gemini_evaluate.is_quantity(cost) and cost["value"] is not None:
        lines.append(f"The levelised cost is {figure_text(cost)}.")
    found = [share_text(coverage), largest_text(capacities)]
    lines += [line for line in found if line is not None]
    lines.append(verdict_text(checks))
    return lines


def heat_shares(coverage: dict[str, Any] | None) -> dict[str, float | None] | None:
    """Return the shares of the heating demand: brine heat, heat-pump electricity, backup.

    ``electricity`` is ``None`` for a coverage stored before gemini gave it (QA-270).
    """
    days = (coverage or {}).get("heating") or []
    demand = sum(day["demand"]["value"] for day in days)
    if demand == 0:
        return None

    def share(key: str) -> float | None:
        if not all(key in day for day in days):
            return None
        return sum(day[key]["value"] for day in days) / demand

    return {
        "geothermal": share("geothermal"),
        "electricity": share("electricity"),
        "backup": share("backup"),
    }


def tiles_of(
    report: dict[str, Any], coverage: dict[str, Any] | None
) -> list[tuple[str, str]]:
    """Return the title and value of each key figure a report has."""
    tiles = [
        (gemini_evaluate.title_of(name), figure_text(report[name]))
        for name in TILE_FIGURES
        if gemini_evaluate.is_quantity(report.get(name))
        and report[name]["value"] is not None
    ]
    shares = heat_shares(coverage)
    if shares is not None and shares["electricity"] is None:
        tiles.append(
            ("Geothermal and heat-pump share", f"{shares['geothermal'] * PERCENT:.0f}%")
        )
    elif shares is not None:
        tiles.append(
            ("Geothermal share of heat", f"{shares['geothermal'] * PERCENT:.0f}%")
        )
        if shares["electricity"] > 0:
            tiles.append(
                (
                    "Heat-pump electricity share",
                    f"{shares['electricity'] * PERCENT:.0f}%",
                )
            )
    return tiles


def capex_rows(report: dict[str, Any], economics: dict[str, Any]) -> list[list[str]]:
    """Return the capital cost by kind, with its unit cost and where that is from."""
    modules = (report.get("capex") or {}).get("modules") or {}
    totals: dict[str, float] = {}
    for item in modules.values():
        totals[item["kind"]] = totals.get(item["kind"], 0) + item["value"]
    prices = economics.get("capex") or {}
    origin = economics.get("file") or "case economics"
    rows = []
    for kind, total in sorted(totals.items(), key=lambda pair: -pair[1]):
        price = prices.get(kind)
        rows.append(
            [
                gemini_evaluate.title_of(kind),
                f"{number_text(total)} MEUR",
                "-"
                if price is None
                else f"{number_text(price['value'])} {price['unit']}",
                "-" if price is None else f"{origin}, capex.{kind}",
            ]
        )
    return rows


def capex_summary(report: dict[str, Any]) -> list[list[str]]:
    """Return the capital cost in three rows: wells, surface plant and other."""
    modules = (report.get("capex") or {}).get("modules") or {}
    totals = dict.fromkeys(CAPEX_GROUPS, 0.0)
    for item in modules.values():
        kind = item["kind"]
        group = next(
            (name for name, kinds in CAPEX_KINDS.items() if kind in kinds),
            SURFACE_GROUP,
        )
        totals[group] += item["value"]
    if not modules:
        return []
    return [[name, f"{number_text(total)} MEUR"] for name, total in totals.items()]
