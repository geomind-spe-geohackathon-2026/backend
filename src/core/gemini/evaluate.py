"""The wrapper around gemini's evaluate report: figures, checks and Pareto."""

from typing import Any

import gemini as gm

from src.core.errors import ValidationFailedError
from src.core.gemini import plant as plant_document

PASSED = "pass"
FAILED = "fail"
NOT_ASSESSED = "not_assessed"


def title_of(name: str) -> str:
    """Return a readable title for a gemini name; gemini has no titles."""
    return name.replace("_", " ").capitalize()


def is_quantity(item: Any) -> bool:
    """Tell whether a report entry is a ``{value, unit}`` figure."""
    return isinstance(item, dict) and {"value", "unit"} <= item.keys()


def kpis_of(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every ``{value, unit}`` figure of the report, in report order."""
    return [
        {
            "name": name,
            "title": title_of(name),
            "value": item["value"],
            "unit": item["unit"],
        }
        for name, item in report.items()
        if is_quantity(item)
    ]


def status_of(requirement: dict[str, Any]) -> str:
    """Map gemini's ``passed`` (true, false, none) to a status."""
    return {True: PASSED, False: FAILED}.get(requirement["passed"], NOT_ASSESSED)


def checks_of(report: dict[str, Any]) -> dict[str, int]:
    """Count the requirements that passed, failed and were not assessed."""
    statuses = [status_of(item) for item in report["requirements"]]
    return {
        "passed": statuses.count(PASSED),
        "failed": statuses.count(FAILED),
        "not_assessed": statuses.count(NOT_ASSESSED),
    }


def amount(item: dict[str, Any] | None) -> str:
    """Write a figure with its unit; a missing one says why."""
    if item is None or item["value"] is None:
        reason = (item or {}).get("reason", "no value")
        return f"missing ({reason})"
    return f"{item['value']:.6g} {item['unit']}"


def message_of(requirement: dict[str, Any]) -> str:
    """Write what a requirement measured against its limit, and where it was worst."""
    text = f"{amount(requirement.get('value'))} against the limit "
    text += amount(requirement.get("limit"))
    worst = requirement.get("worst_step")
    return f"{text} at {worst}" if worst else text


def constraints_of(report: dict[str, Any]) -> list[dict[str, str]]:
    """Return the requirements of the report as constraints."""
    return [
        {
            "name": f"{item['unit_path']}.{item['name']}",
            "title": f"{title_of(item['name'])} ({item['unit_path']})",
            "status": status_of(item),
            "message": message_of(item),
        }
        for item in report["requirements"]
    ]


def capacities_of(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the capacity of each module of the report."""
    return [
        {
            "name": path,
            "title": f"{path} ({item['kind']})",
            "value": item["capacity"]["value"],
            "unit": item["capacity"]["unit"],
        }
        for path, item in report["capacities"].items()
    ]


def summarise(report: dict[str, Any]) -> dict[str, Any]:
    """Return the figures a result keeps from gemini's report in display units."""
    return {
        "summary": {"kpis": kpis_of(report), "checks": checks_of(report)},
        "capacities": capacities_of(report),
        "constraints": constraints_of(report),
    }


def quantity_of(item: dict[str, Any]) -> gm.units.Quantity | None:
    """Return a ``{value, unit}`` figure as gemini's quantity; no value stays none."""
    if item["value"] is None:
        return None
    return gm.units.Quantity(item["value"], item["unit"])


def reduced(report: dict[str, Any], names: list[str]) -> dict[str, Any]:
    """Return what gemini's compare reads of a stored report."""
    figures = {
        name: quantity_of(report[name])
        for name in names
        if is_quantity(report.get(name))
    }
    return {**figures, "verdict": report["verdict"]}


def pareto_flags(reports: list[dict[str, Any]], x: str, y: str) -> list[bool]:
    """Say which stored reports are on the Pareto front of the two named figures."""
    names = list(dict.fromkeys([x, y]))
    entries = [reduced(report, names) for report in reports]
    try:
        found = gm.evaluate.compare(entries, by=names)
    except gm.errors.ValidationError as error:
        raise ValidationFailedError({"x": str(error)}) from error
    return [entry["pareto"] for entry in found]


def describe_plant(content: dict[str, Any]) -> str:
    """Return gemini's text table of the modules of a plant document."""
    return plant_document.from_dict(content).summary()
