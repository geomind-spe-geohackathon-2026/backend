"""The wrapper around gemini's evaluate report: figures, checks and Pareto."""

import math
from datetime import datetime, time, timedelta
from typing import Any

import gemini as gm

from src.core.errors import ValidationFailedError
from src.core.gemini import plant as plant_document

PASSED = "pass"
FAILED = "fail"
NOT_ASSESSED = "not_assessed"
DIMENSIONLESS = "-"
FULL_DIGITS = 12
METRIC_TITLES = {item["name"]: item["title"] for item in gm.evaluate.metrics()}
KIND_MEANINGS = {"cooler": "heat rejected"}
LENGTH_UNIT = "m"
DESIGN_ROLE = "design"
SENSITIVITY_ROLE = "sensitivity"
UNCERTAINTY_ROLE = "uncertainty"
CASE_PREFIX = "case."
CLEAN_DIGITS = 6
LIMIT_DIGITS = 4
PERCENT = 100
PERCENT_UNIT = "%"
FRACTION_UNITS = ("-", "")
COUNT_QUANTITY = "count"
NEAR_SHARE = 0.05
CONDUCTANCE_UNIT = "W/K"
CONDUCTANCE_SCALES = ((1e6, "MW/K"), (1e3, "kW/K"))
UNIT_ALIASES = {"°C": "degC"}
SERVICE_SIDES = {"heating_supply": "min", "cooling_supply": "max"}
SERVICE_NAME = "service"
SERVICE_TITLE = " (service supply rule)"
FAILURE_CHARS = 200


def title_of(name: str) -> str:
    """Return gemini's title of a metric, else a name in words."""
    return METRIC_TITLES.get(name) or name.replace("_", " ").capitalize()


def is_quantity(item: Any) -> bool:
    """Tell whether a report entry is a ``{value, unit}`` figure."""
    return isinstance(item, dict) and {"value", "unit"} <= item.keys()


def kpis_of(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every ``{value, unit}`` figure of the report, in report order."""
    return [
        {
            "name": name,
            "title": item.get("title", title_of(name)),
            "value": item["value"],
            "unit": item["unit"],
            "reason": item.get("reason"),
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


def number(value: float, digits: int = 6) -> str:
    """Write a number in plain digits, or as mantissa x 10^exponent when extreme."""
    if value == 0:
        return "0"
    exponent = math.floor(math.log10(abs(value)))
    if exponent < -4 or exponent >= digits + 3:
        mantissa, _, power = f"{value:.{digits}e}".partition("e")
        return f"{float(mantissa):.{digits}g} x 10^{int(power)}"
    return f"{value:.{digits}g}" if exponent < digits else f"{value:.0f}"


def unit_text(unit: str) -> str:
    """Write a unit; a dimensionless one is written as nothing."""
    return "" if unit == DIMENSIONLESS else f" {unit}"


def reason_text(reason: str) -> str:
    """Write the reason a figure is missing without gemini's code prefix."""
    code, separator, rest = reason.partition(": ")
    return rest if separator and code.replace("_", "").isalpha() else reason


def amount(item: dict[str, Any] | None, digits: int = 6) -> str:
    """Write a figure with its unit; a missing one says why."""
    if item is None or item["value"] is None:
        reason = reason_text((item or {}).get("reason", "no value"))
        return f"missing: {reason}"
    return f"{number(item['value'], digits)}{unit_text(item['unit'])}"


def date_text(moment: str) -> str:
    """Write a timestamp as a date, with the time only when it is not midnight UTC."""
    stamp = datetime.fromisoformat(moment)
    if stamp.utcoffset() in (None, timedelta(0)) and stamp.time() == time(0):
        return stamp.date().isoformat()
    return stamp.strftime("%Y-%m-%d %H:%M") + (
        "" if stamp.utcoffset() in (None, timedelta(0)) else f" {stamp:%z}"
    )


def measured(requirement: dict[str, Any]) -> tuple[str, str]:
    """Write the value and limit of a requirement, with more digits when equal."""
    value, limit = requirement.get("value"), requirement.get("limit")
    texts = amount(value), amount(limit)
    same = texts[0] == texts[1]
    if same and value and limit and value["value"] != limit["value"]:
        return amount(value, FULL_DIGITS), amount(limit, FULL_DIGITS)
    return texts


def first_failure(report: dict[str, Any]) -> str:
    """Write the largest failure group of a run: module, first date and gemini's words.

    A figure of the whole period has no value when steps failed (QA-104); this names
    what to fix first. A run without failed steps gives nothing.
    """
    if not report.get("failed_steps"):
        return ""
    failures = report.get("failures") or {}
    groups = failures.get("groups") if isinstance(failures, dict) else failures
    if not groups:
        return ""
    group = groups[0]
    when = date_text(group["first"]) if group.get("first") else ""
    words = " ".join(str(group.get("message") or group.get("code") or "").split())
    where = ", ".join(filter(None, [group.get("path") or "", when]))
    return f"first failure: {where}: {words[:FAILURE_CHARS]}"


def message_of(requirement: dict[str, Any], failure: str = "") -> str:
    """Write what a requirement measured against its limit, and where it was worst."""
    value, limit = measured(requirement)
    if value.startswith("missing"):
        text = "; ".join(filter(None, [value, failure, f"limit {limit}"]))
    else:
        text = f"{value} against the limit {limit}"
    worst = requirement.get("worst_step")
    return f"{text} at {date_text(worst)}" if worst else text


def subject_of(item: dict[str, Any]) -> str:
    """Return the unit path of a requirement, empty when it has none."""
    return item.get("unit_path") or ""


def clean(value: float) -> float:
    """Return a value without floating point noise."""
    rounded = round(value, CLEAN_DIGITS)
    return 0.0 if rounded == 0 else rounded


def is_fraction(item: dict[str, Any], unit: str, sides: list[float]) -> bool:
    """Tell whether a dimensionless requirement reads as a share of one."""
    plain = unit in FRACTION_UNITS and item.get("quantity") != COUNT_QUANTITY
    return plain and bool(sides) and all(abs(side) <= 1 for side in sides)


def sides_of(
    item: dict[str, Any], limits: dict[str, dict[str, Any]]
) -> tuple[float | None, float | None]:
    """Return a requirement's bounds from the case, in the report's unit.

    ``°C`` in a case is gemini's ``degC``, so a temperature rule keeps its direction.
    """
    given = limits.get(item["name"], {})
    unit = (item.get("value") or {}).get("unit")
    stated = given.get("unit")
    if UNIT_ALIASES.get(stated, stated) not in (None, unit):
        return None, None
    return given.get("min"), given.get("max")


def service_sides(item: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return the bound of gemini's own supply temperature check of a service.

    gemini checks that each heating grid gets at least, and each cooling grid at most,
    the demand's supply temperature, under the name ``<role>_temperature``.
    """
    bound = (item.get("limit") or {}).get("value")
    side = SERVICE_SIDES.get(item.get("role") or "")
    if side == "min":
        return bound, None
    if side == "max":
        return None, bound
    return None, None


def is_service_check(item: dict[str, Any]) -> bool:
    """Tell gemini's service check: ``<role>_temperature`` of a supply role."""
    role = item.get("role") or ""
    return role in SERVICE_SIDES and item["name"] == f"{role}_temperature"


def limit_text(low: float | None, high: float | None, unit: str, fallback: Any) -> str:
    """Write the bounds with their direction; without them the limit gemini reported."""
    suffix = unit_text(unit)
    lower = None if low is None else number(low, LIMIT_DIGITS)
    upper = None if high is None else number(high, LIMIT_DIGITS)
    if lower is not None and upper is not None:
        same = low == high
        return f"= {lower}{suffix}" if same else f"{lower} to {upper}{suffix}"
    if lower is not None:
        return f"≥ {lower}{suffix}"
    if upper is not None:
        return f"≤ {upper}{suffix}"
    return amount(fallback, LIMIT_DIGITS)


def margin_of(
    value: float | None, low: float | None, high: float | None
) -> tuple[float | None, bool]:
    """Return the distance to the nearest bound, and whether that is a near share."""
    sides = [side for side in (low, high) if side is not None]
    if value is None or not sides or low == high:
        return None, False
    margin = min(abs(value - side) for side in sides)
    width = (
        abs(high - low)
        if low is not None and high is not None
        else max(abs(sides[0]), 1)
    )
    return clean(margin), margin < NEAR_SHARE * width


def checked(
    item: dict[str, Any], limits: dict[str, dict[str, Any]], own: bool = False
) -> dict[str, Any]:
    """Return the figures of one requirement, a share of one as a percentage."""
    figure = item.get("value") or {}
    value, unit = figure.get("value"), figure.get("unit", "")
    low, high = service_sides(item) if own else sides_of(item, limits)
    sides = [side for side in (value, low, high) if side is not None]
    scale = PERCENT if is_fraction(item, unit, sides) else 1
    shown = PERCENT_UNIT if scale == PERCENT else unit
    scaled = [None if side is None else side * scale for side in (value, low, high)]
    margin, near = margin_of(*scaled)
    reported = item.get("limit") or {}
    if scale == PERCENT and reported.get("value") is not None:
        reported = {"value": reported["value"] * scale, "unit": shown}
    return {
        "value": None if scaled[0] is None else clean(scaled[0]),
        "unit": shown,
        "limit": limit_text(scaled[1], scaled[2], shown, reported or None),
        "margin": margin,
        "near": near,
    }


def constraints_of(
    report: dict[str, Any],
    limits: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return the requirements of the report as constraints, each name once.

    gemini's own supply temperature check of a service keeps its own bound (at least
    the heating, at most the cooling supply temperature). When the case states a rule of
    the same name, the case's comes first in the report and the service check repeats
    the name on the same module (QA-106: shown twice, with the case's limit, under one
    row key); it is then named ``<module>.<name>.service`` and titled as such.
    """
    given = limits or {}
    failure = first_failure(report)
    seen: set[tuple[str, str]] = set()
    found = []
    for item in report["requirements"]:
        key = (item["name"], subject_of(item))
        repeated = is_service_check(item) and key in seen
        seen.add(key)
        own = is_service_check(item) and (repeated or item["name"] not in given)
        parts = [subject_of(item), item["name"], SERVICE_NAME if repeated else ""]
        found.append(
            {
                "name": ".".join(filter(None, parts)),
                "title": title_of(item["name"]) + (SERVICE_TITLE if repeated else ""),
                "module": subject_of(item) or None,
                "status": status_of(item),
                "message": message_of(item, failure),
                "worst": (item.get("worst_step") or "")[:10] or None,
                **checked(item, given, own),
            }
        )
    return found


def case_limits(content: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Return the bounds of each requirement of a case document by name."""
    if content is None:
        return {}
    return {item["name"]: item for item in content.get("requirements", [])}


def readable(figure: dict[str, Any]) -> dict[str, Any]:
    """Return a figure, a thermal conductance in the largest unit that fits."""
    value, unit = figure["value"], figure["unit"]
    if value is None or unit != CONDUCTANCE_UNIT:
        return figure
    for scale, scaled in CONDUCTANCE_SCALES:
        if abs(value) >= scale:
            return {**figure, "value": value / scale, "unit": scaled}
    return figure


def kind_text(kind: str) -> str:
    """Return a module kind in words, with what its rating measures if not plain."""
    text = title_of(kind)
    meaning = KIND_MEANINGS.get(kind)
    return f"{text}, {meaning}" if meaning else text


def rating_of(path: str, item: dict[str, Any]) -> dict[str, Any]:
    """Return one rated module with its peak use and the share of its rating used.

    ``reason`` is gemini's reason when it has no peak, such as a rating it does not measure
    (QA-213), so a page never reads a missing peak as an unused module.
    """
    capacity = readable(item["capacity"])
    peak = readable(item["peak"])
    return {
        "name": path,
        "title": path,
        "kind": kind_text(item["kind"]),
        "value": capacity["value"],
        "unit": capacity["unit"],
        "peak": peak["value"],
        "peak_unit": peak["unit"],
        "share": item["share"]["value"],
        "reason": peak.get("reason") or item["share"].get("reason"),
    }


def capacities_of(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the rated capacity of each module of the report; lengths are not one."""
    return [
        rating_of(path, item)
        for path, item in report["capacities"].items()
        if item["capacity"]["unit"] != LENGTH_UNIT
    ]


def sizes_of(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return what gemini lists as a rating but is a length, such as a pipe."""
    return [
        rating_of(path, item)
        for path, item in report["capacities"].items()
        if item["capacity"]["unit"] == LENGTH_UNIT
    ]


def tornado_of(run: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Return the rows of a sensitivity study, the largest effect first."""
    found = run.get("found") or {}
    if "rows" not in found:
        return None
    rows = [
        {
            "parameter": item["parameter"].removeprefix(CASE_PREFIX),
            "metric": title_of(item["metric"]),
            "low": amount(item["low"]),
            "high": amount(item["high"]),
            "at_low": item["at_low"]["value"],
            "at_high": item["at_high"]["value"],
            "effect": item["effect"]["value"],
            "unit": item["effect"]["unit"],
            "feasible_low": item.get("feasible_low"),
            "feasible_high": item.get("feasible_high"),
        }
        for item in found["rows"]
    ]
    return sorted(rows, key=lambda row: abs(row["effect"] or 0), reverse=True)


def spread_of(run: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Return the spread of each metric over the draws of an uncertainty study."""
    found = run.get("found") or {}
    if "summary" not in found:
        return None
    samples = found.get("samples", [])
    flags = [item["feasible"] for item in samples if "feasible" in item]
    feasible = sum(flags) if flags else None
    return [
        {
            "name": name,
            "metric": title_of(name),
            "mean": item["mean"]["value"],
            "p5": item["p5"]["value"],
            "p50": item["p50"]["value"],
            "p95": item["p95"]["value"],
            "unit": item["mean"]["unit"],
            "draws": len(samples),
            "feasible": feasible,
        }
        for name, item in found["summary"].items()
    ]


def role_of(run: dict[str, Any]) -> str:
    """Say what a result is: a design, or a test of one under varied inputs."""
    found = run.get("found") or {}
    if "rows" in found:
        return SENSITIVITY_ROLE
    return UNCERTAINTY_ROLE if "summary" in found else DESIGN_ROLE


def design_facts(design: dict[str, Any]) -> dict[str, Any]:
    """Return the doublet count and well depth a design states, when it states them."""
    size = (design.get("size") or {}).get("doublets") or {}
    params = design.get("params") or {}
    depth = params.get("depth") or (params.get("d0") or {}).get("depth") or {}
    return {
        "doublets": size.get("value"),
        "depth": depth.get("value"),
        "depth_unit": depth.get("unit"),
    }


def summarise(
    report: dict[str, Any],
    limits: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the figures a result keeps from gemini's report in display units."""
    return {
        "summary": {"kpis": kpis_of(report), "checks": checks_of(report)},
        "capacities": capacities_of(report),
        "sizes": sizes_of(report),
        "constraints": constraints_of(report, limits),
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
