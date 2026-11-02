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
    """Write how much of the heating demand came from the geothermal plant."""
    days = (coverage or {}).get("heating") or []
    demand = sum(day["demand"]["value"] for day in days)
    if demand == 0:
        return None
    share = sum(day["geothermal"]["value"] for day in days) / demand
    return f"Geothermal covers {share * PERCENT:.0f}% of the heating demand."


def largest_text(capacities: list[dict[str, Any]]) -> str | None:
    """Name the largest rated units in the unit most of the plant uses."""
    power = [item for item in capacities if item["unit"] == "MW"]
    largest = sorted(power, key=lambda item: item["value"] or 0, reverse=True)[:3]
    if not largest:
        return None
    names = ", ".join(
        f"{item['title']} {number_text(item['value'])} MW" for item in largest
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
