"""The numbered sections of a design report, each figure and table with a caption and a reading.

QA-313: a report reads like an engineering report: 1 Summary, 2 Case and demand, 3 Plant
design (3.1 to 3.5), 4 Performance, 5 Economics, 6 Emissions, 7 Studies, 8 Checks, 9
Assumptions and sources. Every figure and table is followed by an italic caption line and a
short paragraph written from the result's own numbers; nothing here is fixed text about one
case. Numbers use thousands separators, four significant digits and a thin space before the
unit (``narrative.figure_text``).
"""

import re
from dataclasses import dataclass, field
from typing import Any

from src.api.v1.reporting.design import figures, narrative
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.models.study import Study
from src.core.gemini import case as gemini_case
from src.core.gemini import evaluate as gemini_evaluate
from src.core.gemini import plant as gemini_plant
from src.core.gemini import study as gemini_study

THIN = narrative.THIN
FLOWSHEET_MARKER = "<!-- flowsheet -->"
HOURS = 24
NUMERIC = re.compile(r"^[-+−]?\d")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
EMPTY_CELLS = ("", "-")
FULL_USE = 0.99
TOP_ITEMS = 3

SUBSURFACE = "Subsurface"
TREATMENT = "Treatment and gas"
HEATING = "Heating"
COOLING = "Cooling"
GRIDS = "Grids"
UNIT_GROUPS = (SUBSURFACE, TREATMENT, HEATING, COOLING, GRIDS)
GROUP_WORDS = {
    GRIDS: ("pipe", "grid", "network"),
    COOLING: ("chill", "cool", "absorption", "adsorption"),
    TREATMENT: ("degas", "flare", "gas", "separ", "filter", "sand", "chemic", "treat"),
    SUBSURFACE: ("drill", "well", "production", "injection", "doublet", "reservoir"),
}
"""Words of a module kind that place it in a group, tried in this order; the rest is heating."""

CO2_SOURCES = {
    "direct": "Fuel burnt in the plant",
    "methane": "Methane released",
    "electricity": "Grid electricity bought",
}
OPEX_WORDS = {"co2": "CO2 price"}
UNMET_SHARE = 1e-4
"""The share of a service's demand below which its unmet energy is residue: 0.01 %."""
RELATED_KINDS = ("sensitivity", "sample")
"""Study kinds whose results the Studies section names beside an optimisation (QA-338)."""
RATIO_TITLES = {"cop": "Heat per bought electricity", "heat_pump_cop": "Heat pump COP"}
"""Titles of the plant ratio and the heat pumps' COP when gemini names neither (QA-322)."""
ENERGY_UNIT = "MWh"


@dataclass
class Numbers:
    """Count the figures and tables of one section: Figure 3.1, Table 3.2."""

    section: int
    figures: int = 0
    tables: int = 0

    def figure(self, caption: str) -> str:
        self.figures += 1
        return f"*Figure {self.section}.{self.figures} - {caption}*"

    def table(self, caption: str) -> str:
        self.tables += 1
        return f"*Table {self.section}.{self.tables} - {caption}*"


@dataclass
class Inputs:
    """What every section reads: the result, its study, run, case, limits and economics."""

    result: Result
    study: Study | None
    run: Run | None
    case: CaseVersion | None
    limits: dict[str, dict[str, Any]]
    economics: dict[str, Any]
    related: list[tuple[Study, Result | None]] = field(default_factory=list)
    report: dict[str, Any] = field(init=False)
    coverage: dict[str, Any] | None = field(init=False)

    def __post_init__(self) -> None:
        self.report = self.result.content["report"]
        self.coverage = self.result.content.get("coverage")


def is_number_cell(cell: str) -> bool:
    found = cell.strip()
    return bool(NUMERIC.match(found)) and not DATE.match(found)


def table(headers: list[str], rows: list[list[str]]) -> str:
    """Write a Markdown table; a column of numbers is right-aligned."""
    numeric = [
        any(is_number_cell(row[at]) for row in rows)
        and all(
            is_number_cell(row[at]) or row[at].strip() in EMPTY_CELLS for row in rows
        )
        for at in range(len(headers))
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---:" if flag else "---" for flag in numeric) + " |",
    ]
    lines += [
        "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |"
        for row in rows
    ]
    return "\n".join(lines)


def shown(item: Any) -> bool:
    return gemini_evaluate.is_quantity(item) and item["value"] is not None


def text(item: dict[str, Any]) -> str:
    return narrative.figure_text(item)


def percent(share: float) -> str:
    return narrative.percent_text(share)


def joined(words: list[str]) -> str:
    """Join words as a list in a sentence: ``a``, ``a and b``, ``a, b and c``."""
    if len(words) <= 1:
        return "".join(words)
    return f"{', '.join(words[:-1])} and {words[-1]}"


def block(*parts: str | None) -> str:
    return "\n\n".join(part for part in parts if part)


def sentences(*parts: str | None) -> str:
    return " ".join(part for part in parts if part)


def summary(inputs: Inputs, numbers: Numbers) -> str:
    report, coverage = inputs.report, inputs.coverage
    parts = gemini_evaluate.summarise(report)
    lines = narrative.summary_sentences(
        report, parts["capacities"], coverage, inputs.result.summary["checks"]
    )
    co2 = report.get("co2")
    if shown(co2):
        lines.insert(-1, f"It emits {text(co2)} of CO2 over the run.")
    risk = main_risk(inputs)
    if risk:
        lines.append(risk)
    tiles = narrative.tiles_of(report, coverage)
    if not tiles:
        return " ".join(lines)
    picture = figures.image_line(figures.kpi_tiles(tiles), "Key figures")
    caption = numbers.figure("Key figures of the design")
    return block(picture, caption, " ".join(lines))


def main_risk(inputs: Inputs) -> str | None:
    """Name the main risk the result shows: a failed check, an unassessed one, or a driver."""
    constraints = gemini_evaluate.summarise(inputs.report, inputs.limits)["constraints"]
    failed = [item for item in constraints if item["status"] == gemini_evaluate.FAILED]
    if failed:
        return f"The main risk is the failed check {check_name(failed[0])}."
    unknown = [
        item for item in constraints if item["status"] == gemini_evaluate.NOT_ASSESSED
    ]
    if unknown:
        return (
            f"The main open point is {check_name(unknown[0])}, which could not be "
            f"assessed: {unknown[0]['message']}."
        )
    tornado = gemini_evaluate.tornado_of(inputs.result.content.get("run") or {})
    if tornado:
        top = tornado[0]
        return (
            f"The largest uncertainty is {top['parameter']}, which moves "
            f"{top['metric'].lower()} by {text({'value': top['effect'], 'unit': top['unit']})}."
        )
    return None


def check_name(item: dict[str, Any]) -> str:
    if not item["module"]:
        return item["title"].lower()
    return f"{item['title'].lower()} ({narrative.module_words(item['module'])})"


def case_section(inputs: Inputs, numbers: Numbers) -> str:
    case = inputs.case
    if case is None:
        return "The result names no saved case version, so its inputs cannot be shown."
    content = case.content
    lead = sentences(
        f"The design runs on case {content.get('name') or 'without a name'}, "
        f"version {case.number}.",
        period_text(content.get("time") or {}),
    )
    site = site_rows(content.get("site") or {})
    parts = [lead]
    if site:
        parts += [
            table(["Quantity", "Value", "Uncertainty"], site),
            numbers.table("Site, reservoir and fluid values of the case"),
            site_reading(content.get("site") or {}, site),
        ]
    demand = demand_rows(content.get("demand") or {}, inputs.coverage)
    if demand:
        parts += [
            table(
                [
                    "Service",
                    "Supply",
                    "Return",
                    "Annual demand",
                    "Peak (daily mean)",
                    "Met",
                ],
                demand,
            ),
            numbers.table("Demand of each service and how much of it was met"),
            demand_reading(content.get("demand") or {}, inputs.coverage),
        ]
    return block(*parts)


def period_of(time: dict[str, Any]) -> str | None:
    start, end, step = time.get("start"), time.get("end"), time.get("step")
    if not start or not end:
        return None
    every = f", in steps of {text(step)}" if shown(step) else ""
    return f"{start} to {end}{every}"


def period_text(time: dict[str, Any]) -> str | None:
    period = period_of(time)
    return None if period is None else f"The simulation runs from {period}."


def quantities(node: Any, prefix: str = "") -> list[tuple[str, dict[str, Any]]]:
    """Return every ``{value, unit}`` of a nested case dict with its dotted path."""
    found = []
    if not isinstance(node, dict):
        return found
    if "value" in node and not isinstance(node["value"], dict):
        return [(prefix, node)]
    for key, child in node.items():
        found += quantities(child, f"{prefix}.{key}" if prefix else key)
    return found


def path_words(path: str) -> str:
    words = path.replace(".", " ").replace("_", " ")
    return words[:1].upper() + words[1:]


def value_text(item: dict[str, Any]) -> str:
    value = item.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return str(value)
    return text({"value": value, "unit": item.get("unit") or "-"})


def spread_text(item: dict[str, Any]) -> str:
    found = item.get("uncertainty")
    if not isinstance(found, dict):
        return "-"
    low, high = found.get("min"), found.get("max")
    kind = found.get("kind") or "range"
    if low is None or high is None:
        return kind
    unit = item.get("unit") or "-"
    return (
        f"{kind}, {narrative.number_text(low)} to {text({'value': high, 'unit': unit})}"
    )


def site_rows(site: dict[str, Any]) -> list[list[str]]:
    return [
        [path_words(path), value_text(item), spread_text(item)]
        for path, item in quantities(site)
    ]


def site_reading(site: dict[str, Any], rows: list[list[str]]) -> str:
    values = dict(quantities(site))
    named = [
        f"{words} {value_text(values[path])}"
        for path, words in (
            ("reservoir.reference_depth", "a depth of"),
            ("reservoir.thickness", "a thickness of"),
            ("reservoir.permeability", "a permeability of"),
        )
        if path in values
    ]
    uncertain = sum(1 for row in rows if row[2] != "-")
    first = f"The reservoir has {joined(named)}." if named else None
    second = (
        f"{uncertain} of the {len(rows)} values carry an uncertainty range, which the "
        "studies of section 7 can vary."
        if uncertain
        else f"None of the {len(rows)} values carries an uncertainty range."
    )
    return sentences(first, second)


def service_days(coverage: dict[str, Any] | None, service: str) -> list[dict[str, Any]]:
    return (coverage or {}).get(service) or []


def demand_stats(days: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not days:
        return None
    demand = sum(day["demand"]["value"] for day in days)
    short = sum(day["short"]["value"] for day in days)
    unit = days[0]["demand"]["unit"]
    peak = max(days, key=lambda day: day["demand"]["value"])
    return {
        "demand": {"value": demand, "unit": unit},
        "short": {"value": short, "unit": unit},
        "met": None if demand == 0 else (demand - short) / demand,
        "peak": {"value": peak["demand"]["value"] / HOURS, "unit": "MW"},
        "peak_date": peak["date"],
        "mean": {"value": demand / len(days) / HOURS, "unit": "MW"},
    }


def demand_rows(
    demand: dict[str, Any], coverage: dict[str, Any] | None
) -> list[list[str]]:
    rows = []
    for service, given in demand.items():
        if not isinstance(given, dict):
            continue
        stats = demand_stats(service_days(coverage, service))
        supply, back = given.get("supply_temperature"), given.get("return_temperature")
        rows.append(
            [
                service.capitalize(),
                value_text(supply) if isinstance(supply, dict) else "-",
                value_text(back) if isinstance(back, dict) else "-",
                "-" if stats is None else text(stats["demand"]),
                "-" if stats is None else text(stats["peak"]),
                "-" if stats is None or stats["met"] is None else percent(stats["met"]),
            ]
        )
    return rows


def demand_reading(demand: dict[str, Any], coverage: dict[str, Any] | None) -> str:
    lines = []
    for service, given in demand.items():
        stats = demand_stats(service_days(coverage, service))
        if stats is None or not isinstance(given, dict):
            continue
        lines.append(
            f"{service.capitalize()} demand totals {text(stats['demand'])} with a peak "
            f"daily mean of {text(stats['peak'])} on {stats['peak_date']} and a mean of "
            f"{text(stats['mean'])}."
        )
    sources = sorted(
        {
            f"{power['file']} ({power.get('column') or 'one column'})"
            for given in demand.values()
            if isinstance(given, dict)
            for power in [given.get("power")]
            if isinstance(power, dict) and power.get("file")
        }
    )
    if sources:
        lines.append(f"The demand profiles come from {joined(sources)}.")
    if not lines:
        return "The result has no daily coverage, so the demand is not summed here."
    return " ".join(lines)


def group_of(kind: str) -> str:
    for group, words in GROUP_WORDS.items():
        if any(word in kind for word in words):
            return group
    return HEATING


def plant_units(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return each module of the report with its kind, group, rating and capital cost."""
    capex = (report.get("capex") or {}).get("modules") or {}
    raw = report.get("capacities") or {}
    rated = {
        item["name"]: item
        for item in gemini_evaluate.summarise(report)["capacities"]
        + gemini_evaluate.summarise(report)["sizes"]
    }
    names = list(dict.fromkeys([*capex, *raw]))
    units = []
    for name in names:
        kind = (capex.get(name) or raw.get(name) or {}).get("kind") or ""
        cost = capex.get(name)
        units.append(
            {
                "name": name,
                "kind": kind,
                "group": group_of(kind),
                "rated": rated.get(name),
                "capex": None if cost is None else cost["value"],
            }
        )
    return units


def design_section(inputs: Inputs, numbers: Numbers) -> str:
    result, study = inputs.result, inputs.study
    kind = gemini_plant.type_of(result.content["design"])
    titles = {item["kind"]: item["title"] for item in gemini_study.kinds()}
    kind_title = "" if study is None else titles.get(study.kind, "")
    origin = f" from a study of kind {kind_title}" if kind_title else ""
    lead = f"Design {result.name}{origin}, plant type {narrative.spaced(kind)}."
    units = plant_units(inputs.report)
    total = sum(unit["capex"] or 0 for unit in units)
    parts = [
        lead,
        FLOWSHEET_MARKER,
        numbers.figure("Process flowsheet of the plant"),
        flowsheet_reading(result.content["design"], units),
    ]
    for at, group in enumerate(UNIT_GROUPS, start=1):
        members = [unit for unit in units if unit["group"] == group]
        parts.append(f"### 3.{at} {group}")
        if not members:
            parts.append(f"The plant has no {group.lower()} units.")
            continue
        parts += [
            table(
                ["Module", "Kind", "Rated", "Peak", "Used", "Capital cost"],
                [unit_row(unit) for unit in members],
            ),
            numbers.table(f"{group} units: rating, use and capital cost"),
            group_reading(group, members, total),
        ]
    return block(*parts)


def flowsheet_reading(design: dict[str, Any], units: list[dict[str, Any]]) -> str:
    structure = gemini_plant.structure_of(design)
    modules, links = structure["modules"], structure["connections"]
    streams = sorted({item.get("stream") or item.get("kind") or "" for item in links})
    counts = [
        f"{sum(1 for unit in units if unit['group'] == group)} {group.lower()}"
        for group in UNIT_GROUPS
        if any(unit["group"] == group for unit in units)
    ]
    return sentences(
        f"The flowsheet shows the {len(modules)} modules of the plant and the "
        f"{len(links)} connections between them"
        + (
            f", carrying {joined([item for item in streams if item])}."
            if streams
            else "."
        ),
        f"The costed units fall into {joined(counts)} units; "
        "subsections 3.1 to 3.5 give each group with its size and use."
        if counts
        else None,
    )


def unit_row(unit: dict[str, Any]) -> list[str]:
    rated = unit["rated"]
    rating = peak = used = "-"
    if rated is not None:
        rating = (
            text({"value": rated["value"], "unit": rated["unit"]})
            if rated["value"] is not None
            else "-"
        )
        if rated["peak"] is not None:
            peak = text({"value": rated["peak"], "unit": rated["peak_unit"]})
        if rated["share"] is not None:
            used = percent(rated["share"])
    cost = (
        "-" if unit["capex"] is None else text({"value": unit["capex"], "unit": "MEUR"})
    )
    return [
        narrative.module_words(unit["name"]),
        gemini_evaluate.title_of(unit["kind"]) if unit["kind"] else "-",
        rating,
        peak,
        used,
        cost,
    ]


def group_reading(group: str, members: list[dict[str, Any]], total: float) -> str:
    cost = sum(unit["capex"] or 0 for unit in members)
    count = len(members)
    first = f"{count} unit{'s' if count > 1 else ''} make{'' if count > 1 else 's'} up "
    first += f"the {group.lower()} part"
    if cost and total:
        first += (
            f", with a capital cost of {text({'value': cost, 'unit': 'MEUR'})}, "
            f"{percent(cost / total)} of the plant's total"
        )
    first += "."
    largest = max(members, key=lambda unit: unit["capex"] or 0)
    second = None
    if largest["capex"]:
        second = f"The largest is {narrative.module_words(largest['name'])}"
        rated = largest["rated"]
        if rated is not None and rated["value"] is not None:
            second += (
                f", rated {text({'value': rated['value'], 'unit': rated['unit']})}"
            )
            if rated["share"] is not None:
                second += (
                    f", which ran at up to {percent(rated['share'])} of its rating"
                )
        second += "."
    full = [
        narrative.module_words(unit["name"])
        for unit in members
        if unit["rated"] is not None
        and unit["rated"]["share"] is not None
        and unit["rated"]["share"] >= FULL_USE
    ]
    third = (
        f"{joined(full)} ran at {'its' if len(full) == 1 else 'their'} full rating, so "
        f"{'it limits' if len(full) == 1 else 'they limit'} what the plant can deliver."
        if full
        else None
    )
    return sentences(first, second, third)


def performance(inputs: Inputs, numbers: Numbers) -> str:
    report, coverage = inputs.report, inputs.coverage
    energy = narrative.grouped_figures(report).get(narrative.ENERGY_GROUP) or []
    energy += fuel_rows(report) + ratio_rows(report)
    parts = []
    if energy:
        parts += [
            table(["Figure", "Value"], energy),
            numbers.table("Energy balance of the run"),
            energy_reading(report, coverage),
        ]
    if coverage is None:
        parts.append("Made before daily coverage existed.")
        return block(*parts)
    services = [(service, days) for service, days in coverage.items() if days]
    parts += [
        figures.image_line(figures.day_strips(coverage), "Days covered"),
        numbers.figure("Source that covered the demand on each day"),
        days_reading(services),
    ]
    for service, days in services:
        title = f"{service.capitalize()}: demand and supply"
        main, other = figures.labels_of(service, days)
        chart = figures.supply_chart(title, days, (main, other or "Other units"))
        parts += [
            figures.image_line(chart, title),
            numbers.figure(f"{service.capitalize()}: daily mean demand and supply"),
            supply_reading(service, days, coverage),
        ]
    rows = performance_rows(services)
    headers = ["Service", "Main supply", "Days", "Other supply", "Days", "Short"]
    parts += [
        table([*headers, "No demand"], rows),
        numbers.table("Days of each service by the units that covered them"),
    ]
    return block(*parts)


def performance_rows(
    services: list[tuple[str, list[dict[str, Any]]]],
) -> list[list[str]]:
    """Return per service the days its main and other units covered, short and idle."""
    rows = []
    for service, days in services:
        main, other = figures.labels_of(service, days)
        count = day_counts(days)
        rows.append(
            [
                service.capitalize(),
                main,
                str(count["geothermal"]),
                other or "-",
                str(count["backup"]) if other else "-",
                str(count["short"]),
                str(count["none"]),
            ]
        )
    return rows


def day_counts(days: list[dict[str, Any]]) -> dict[str, int]:
    """Count the days by source; a day with no demand counts as none (QA-322)."""
    count = {name: 0 for name in ("geothermal", "backup", "short", "none")}
    for day in days:
        count["none" if day.get("no_demand") else day["source"]] += 1
    return count


def fuel_rows(report: dict[str, Any]) -> list[list[str]]:
    """Return the fuel burned on site and its part not bought, the produced gas (QA-323).

    The gas bought alone made a boiler look above 100 % efficient: the plant also burns the gas
    its degasser takes out of the brine. gemini gives the fuel burned as ``co2.fuel_energy``.
    """
    fuel = (report.get("co2") or {}).get("fuel_energy")
    if not shown(fuel) or not fuel["value"]:
        return []
    rows = [["Fuel burned on site", text(fuel)]]
    produced = produced_gas(report)
    if produced is not None:
        rows.append(
            ["Produced gas burned (fuel burned less gas bought)", text(produced)]
        )
    return rows


def produced_gas(report: dict[str, Any]) -> dict[str, Any] | None:
    fuel = (report.get("co2") or {}).get("fuel_energy")
    bought = report.get("gas_bought")
    if not shown(fuel) or fuel["unit"] != ENERGY_UNIT:
        return None
    if not shown(bought) or bought["unit"] != ENERGY_UNIT:
        return None
    return {"value": max(fuel["value"] - bought["value"], 0.0), "unit": ENERGY_UNIT}


def ratio_title(name: str) -> str:
    return gemini_evaluate.METRIC_TITLES.get(name) or RATIO_TITLES[name]


def ratio_rows(report: dict[str, Any]) -> list[list[str]]:
    """Return the plant's heat per bought electricity beside the heat pumps' COP (QA-322)."""
    return [
        [ratio_title(name), text(report[name])]
        for name in RATIO_TITLES
        if shown(report.get(name))
    ]


def energy_reading(report: dict[str, Any], coverage: dict[str, Any] | None) -> str:
    heat = report.get("heat_delivered")
    stats = demand_stats(service_days(coverage, "heating"))
    first = None
    if shown(heat) and stats is not None and stats["met"] is not None:
        first = (
            f"The plant delivers {text(heat)} of heat against a demand of "
            f"{text(stats['demand'])}, so it meets {percent(stats['met'])} of it."
        )
    elif shown(heat):
        first = f"The plant delivers {text(heat)} of heat."
    boiler = report.get("boiler_heat")
    second = None
    if shown(boiler) and shown(heat) and heat["value"]:
        second = (
            f"The boilers give {text(boiler)}, {percent(boiler['value'] / heat['value'])} "
            "of the heat delivered."
        )
    fuel = (report.get("co2") or {}).get("fuel_energy")
    produced = produced_gas(report)
    fuel_line = None
    if shown(fuel) and fuel["value"] and produced is not None:
        fuel_line = (
            f"The plant burns {text(fuel)} of fuel on site: "
            f"{text(report['gas_bought'])} of gas bought and {text(produced)} of gas "
            "produced with the brine."
        )
    bought = [
        f"{text(report[name])} of {word}"
        for name, word in (("electricity_bought", "electricity"), ("gas_bought", "gas"))
        if shown(report.get(name))
    ]
    third = f"It buys {joined(bought)}." if bought else None
    fourth = narrative.share_text(coverage)
    return (
        sentences(first, second, fuel_line, third, fourth, ratio_reading(report))
        or "The run gives no energy figures."
    )


def ratio_reading(report: dict[str, Any]) -> str | None:
    cop, pump = report.get("cop"), report.get("heat_pump_cop")
    first = (
        f"Per unit of electricity bought the plant delivers {text(cop)} units of heat, "
        "a ratio of the whole plant, not the COP of a machine."
        if shown(cop)
        else None
    )
    second = (
        f"The heat pumps give {text(pump)} units of heat per unit of the electricity "
        "they take, their COP."
        if shown(pump)
        else None
    )
    return sentences(first, second) or None


def days_reading(services: list[tuple[str, list[dict[str, Any]]]]) -> str:
    """Say per service how many days each kind of unit covered, named from gemini's labels."""
    lines = []
    for service, days in services:
        count = day_counts(days)
        main, other = figures.labels_of(service, days)
        asked = len(days) - count["none"]
        first = f"Of the {len(days)} {service} days, {asked} had a demand"
        first += f" and {count['none']} had none." if count["none"] else "."
        parts = [f"{count['geothermal']} were covered by {main} alone"]
        if other:
            parts.append(f"{count['backup']} also needed {other}")
        parts.append(f"{count['short']} fell short")
        lines.append(f"{first} Of the days with a demand, {joined(parts)}.")
    return " ".join(lines) or "The run has no days with a demand."


def supply_reading(
    service: str, days: list[dict[str, Any]], coverage: dict[str, Any]
) -> str:
    stats = demand_stats(days)
    if stats is None:
        return ""
    first = (
        f"{service.capitalize()} demand peaks at {text(stats['peak'])} (daily mean) on "
        f"{stats['peak_date']} and averages {text(stats['mean'])}."
    )
    main, other = figures.labels_of(service, days)
    backup = [day for day in days if day["backup"]["value"] > 0]
    second = None
    if backup and other:
        top = max(backup, key=lambda day: day["backup"]["value"])
        second = (
            f"{other} runs on {len(backup)} days, at most "
            f"{text({'value': top['backup']['value'] / HOURS, 'unit': 'MW'})} on "
            f"{top['date']}."
        )
    elif other:
        second = f"{other} is never needed."
    else:
        second = f"{main} gives the whole supply."
    third = (
        f"{text(stats['short'])} of demand is not met."
        if is_unmet(stats)
        else "All demand is met."
    )
    return sentences(first, second, third)


def is_unmet(stats: dict[str, Any]) -> bool:
    """Tell an unmet demand from floating-point residue: below ``UNMET_SHARE`` is met (QA-338)."""
    demand = stats["demand"]["value"]
    return stats["short"]["value"] > UNMET_SHARE * demand if demand else False


def economics(inputs: Inputs, numbers: Numbers) -> str:
    result, report = inputs.result, inputs.report
    source = f"From case version {result.case_version}, plant version {result.plant_version}."
    rows = narrative.grouped_figures(report).get(narrative.ECONOMICS_GROUP) or []
    if not rows:
        return block(source, "No costs.")
    parts = [
        source,
        table(["Figure", "Value"], rows),
        numbers.table("Cost figures of the design"),
        cost_reading(report),
    ]
    shares = capex_groups(report)
    if shares:
        parts += [
            table(["Capital cost", "Amount", "Share"], shares),
            numbers.table("Capital cost by part of the plant"),
            capex_group_reading(shares),
        ]
    kinds = narrative.capex_rows(report, inputs.economics)
    if kinds:
        parts += [
            table(["Item", "Amount", "Unit cost", "Source"], kinds),
            numbers.table("Capital cost by kind of unit, with its unit cost"),
            capex_kind_reading(report),
        ]
    components = opex_rows(report)
    if components:
        parts += [
            table(["Operating cost", "Amount", "Share"], components),
            numbers.table("Yearly operating cost by component"),
            opex_reading(report),
        ]
    return block(*parts)


def cost_reading(report: dict[str, Any]) -> str:
    lcts, capex, opex = report.get("lcts"), report.get("capex"), report.get("opex")
    first = None
    if shown(lcts):
        cost = lcts.get("annualised_cost")
        first = f"The levelised cost of thermal supply is {text(lcts)}"
        if shown(cost):
            first += f", from an annualised cost of {text(cost)}"
        first += "."
    second = None
    if shown(capex) and shown(opex):
        second = f"The plant costs {text(capex)} to build and {text(opex)} to run."
    elif shown(capex):
        second = f"The plant costs {text(capex)} to build."
    missing = [
        gemini_evaluate.title_of(name).lower()
        for name in ("capex", "opex", "lcts")
        if gemini_evaluate.is_quantity(report.get(name))
        and report[name]["value"] is None
    ]
    third = (
        f"No value is given for {joined(missing)}, as the case lacks a price."
        if missing
        else None
    )
    return sentences(first, second, third) or "The run gives no cost figures."


def capex_total(report: dict[str, Any]) -> float:
    modules = (report.get("capex") or {}).get("modules") or {}
    return sum(item["value"] for item in modules.values())


def capex_groups(report: dict[str, Any]) -> list[list[str]]:
    total = capex_total(report)
    rows = narrative.capex_summary(report)
    if not total:
        return [[*row, "-"] for row in rows]
    modules = (report.get("capex") or {}).get("modules") or {}
    amounts = dict.fromkeys(narrative.CAPEX_GROUPS, 0.0)
    for item in modules.values():
        group = next(
            (
                name
                for name, kinds in narrative.CAPEX_KINDS.items()
                if item["kind"] in kinds
            ),
            narrative.SURFACE_GROUP,
        )
        amounts[group] += item["value"]
    return [[name, amount, percent(amounts[name] / total)] for name, amount in rows]


def capex_group_reading(rows: list[list[str]]) -> str:
    ranked = [row for row in rows if row[2] != "-"]
    if not ranked:
        return "The capital cost has no total to share."
    top = max(ranked, key=lambda row: float(row[2].split(THIN)[0].replace(",", "")))
    return (
        f"{top[0]} take the largest share of the capital cost, {top[2]} "
        f"({top[1]}); the table splits the rest."
    )


def capex_kind_reading(report: dict[str, Any]) -> str:
    modules = (report.get("capex") or {}).get("modules") or {}
    totals: dict[str, float] = {}
    for item in modules.values():
        totals[item["kind"]] = totals.get(item["kind"], 0) + item["value"]
    total = sum(totals.values())
    if not total:
        return "No unit has a capital cost."
    ranked = sorted(totals.items(), key=lambda pair: -pair[1])[:TOP_ITEMS]
    words = [
        f"{gemini_evaluate.title_of(kind).lower()} ({percent(value / total)})"
        for kind, value in ranked
    ]
    share = sum(value for _, value in ranked) / total
    return (
        f"The largest items are {joined(words)}; together they make "
        f"{percent(share)} of the capital cost."
    )


def opex_rows(report: dict[str, Any]) -> list[list[str]]:
    opex = report.get("opex") or {}
    components = {
        name: item
        for name, item in (opex.get("components") or {}).items()
        if shown(item)
    }
    total = sum(item["value"] for item in components.values())
    return [
        [
            OPEX_WORDS.get(name, gemini_evaluate.title_of(name)),
            text(item),
            percent(item["value"] / total) if total else "-",
        ]
        for name, item in sorted(components.items(), key=lambda pair: -pair[1]["value"])
    ]


def opex_reading(report: dict[str, Any]) -> str:
    components = {
        name: item
        for name, item in ((report.get("opex") or {}).get("components") or {}).items()
        if shown(item)
    }
    total = sum(item["value"] for item in components.values())
    if not total:
        return "The run has no operating cost."
    ranked = sorted(components.items(), key=lambda pair: -pair[1]["value"])
    name, item = ranked[0]
    first = (
        f"{OPEX_WORDS.get(name, gemini_evaluate.title_of(name))} is the largest "
        f"operating cost, {text(item)} or {percent(item['value'] / total)} of the total."
    )
    none = [
        OPEX_WORDS.get(key, gemini_evaluate.title_of(key)).lower()
        for key, value in components.items()
        if value["value"] == 0
    ]
    second = f"The run has no {joined(none)} cost." if none else None
    return sentences(first, second)


def emissions(inputs: Inputs, numbers: Numbers) -> str:
    report = inputs.report
    co2 = report.get("co2")
    if not shown(co2):
        return "The run gives no CO2 emissions."
    sources = {
        name: co2[name] for name in co2 if name in CO2_SOURCES and shown(co2[name])
    }
    total = co2["value"]
    rows = [
        [
            CO2_SOURCES[name],
            text(item),
            percent(item["value"] / total) if total else "-",
        ]
        for name, item in sources.items()
    ]
    rows.append(["Total", text(co2), percent(1.0) if total else "-"])
    return block(
        table(["Source", "CO2", "Share"], rows),
        numbers.table("CO2 emissions of the run by source"),
        emissions_reading(report, sources),
    )


def emissions_reading(report: dict[str, Any], sources: dict[str, Any]) -> str:
    co2 = report["co2"]
    first = f"The plant emits {text(co2)} of CO2 over the run"
    energy = [
        report[name]["value"]
        for name in ("heat_delivered", "cold_delivered")
        if shown(report.get(name)) and report[name]["unit"] == "MWh"
    ]
    if co2["unit"] == "kt" and sum(energy):
        intensity = co2["value"] * 1e6 / sum(energy)
        first += f", {text({'value': intensity, 'unit': 'kg/MWh'})} of energy delivered"
    first += "."
    second = None
    if sources and co2["value"]:
        name, item = max(sources.items(), key=lambda pair: pair[1]["value"])
        second = (
            f"{CO2_SOURCES[name]} is the largest source, "
            f"{percent(item['value'] / co2['value'])} of the total."
        )
    used = [
        f"{text(co2[name])} of {word}"
        for name, word in (("fuel_energy", "fuel"), ("grid_energy", "grid electricity"))
        if shown(co2.get(name))
    ]
    third = f"They come from {joined(used)}." if used else None
    return sentences(first, second, third)


def studies(inputs: Inputs, numbers: Numbers) -> str:
    run = inputs.result.content.get("run") or {}
    parts = []
    origin = study_origin(inputs.study)
    if origin:
        parts.append(origin)
    tornado = gemini_evaluate.tornado_of(run)
    if tornado:
        rows = [
            [
                item["parameter"],
                item["metric"],
                f"{item['low']} to {item['high']}",
                text({"value": item["effect"], "unit": item["unit"]}),
            ]
            for item in tornado
        ]
        parts += [
            table(["Value", "Metric", "Moved", "Effect"], rows),
            numbers.table("Sensitivity: effect of each uncertain value, largest first"),
            tornado_reading(tornado),
        ]
    spread = gemini_evaluate.spread_of(run)
    if spread:
        rows = [
            [
                item["metric"],
                *(
                    text({"value": item[key], "unit": item["unit"]})
                    for key in ("p5", "p50", "p95")
                ),
            ]
            for item in spread
        ]
        parts += [
            table(["Metric", "P5", "P50", "P95"], rows),
            numbers.table(f"Uncertainty: spread over {spread[0]['draws']} draws"),
            spread_reading(spread),
        ]
    search = run.get("found") or {}
    if isinstance(search, dict) and isinstance(search.get("history"), list):
        parts += optimisation(search, inputs, numbers)
    elif isinstance(search, dict) and isinstance(search.get("front"), list):
        parts.append(evolution_reading(search))
    if not tornado and not spread:
        parts.append(related_reading(inputs))
    return block(*parts)


def parameter_value(item: Any) -> str:
    if isinstance(item, dict) and "value" in item:
        return value_text(item)
    if isinstance(item, (int, float)) and not isinstance(item, bool):
        return narrative.number_text(item)
    return str(item)


def parameter_number(item: Any) -> float | None:
    found = item.get("value") if isinstance(item, dict) else item
    if isinstance(found, (int, float)) and not isinstance(found, bool):
        return float(found)
    return None


def is_feasible_trial(trial: dict[str, Any]) -> bool:
    return trial.get("value") is not None and not trial.get("violation")


def optimisation(search: dict[str, Any], inputs: Inputs, numbers: Numbers) -> list[str]:
    """Return the table and reading of a ``minimize`` search: variables, start, best (QA-338).

    gemini's ``found`` holds ``best`` and the ``history`` of every trial with its parameters;
    the start is the first trial, the explored range the lowest and highest value tried.
    """
    history = [item for item in search["history"] if isinstance(item, dict)]
    best = search.get("best") or {}
    if not history:
        return []
    start = history[0]
    chosen = best.get("parameters") or {}
    rows = []
    for name, value in chosen.items():
        tried = [
            number
            for trial in history
            for number in [parameter_number((trial.get("parameters") or {}).get(name))]
            if number is not None
        ]
        unit = value.get("unit") if isinstance(value, dict) else None
        explored = "-"
        if tried:
            low, high = min(tried), max(tried)
            explored = f"{narrative.number_text(low)} to " + (
                text({"value": high, "unit": unit})
                if unit
                else narrative.number_text(high)
            )
        rows.append(
            [
                name.removeprefix("params."),
                parameter_value((start.get("parameters") or {}).get(name, "-")),
                parameter_value(value),
                explored,
            ]
        )
    parts = []
    if rows:
        parts += [
            table(["Variable", "First trial", "Best", "Explored"], rows),
            numbers.table("Optimisation: the variables searched, first trial and best"),
        ]
    parts.append(search_reading(search, history, inputs))
    return parts


def search_reading(
    search: dict[str, Any], history: list[dict[str, Any]], inputs: Inputs
) -> str:
    feasible = sum(1 for trial in history if is_feasible_trial(trial))
    count = search.get("evaluations") or len(history)
    first = f"The search ran {count} trials; {feasible} of them met every rule."
    objective = (inputs.study.settings or {}).get("objective") if inputs.study else None
    title = (
        gemini_evaluate.title_of(objective).lower() if objective else "the objective"
    )
    best = search.get("best") or {}
    start = next((trial for trial in history if is_feasible_trial(trial)), None)
    second = None
    if shown(best) and start is not None:
        second = (
            f"The first feasible trial gave {title} {text(start)}; the best gives "
            f"{text(best)}."
        )
    elif shown(best):
        second = f"The best trial gives {title} {text(best)}."
    third = (
        "The search found no feasible design."
        if search.get("feasible") is False
        else None
    )
    return sentences(first, second, third)


def evolution_reading(search: dict[str, Any]) -> str:
    budget = search.get("budget") or {}
    objectives = [
        gemini_evaluate.title_of(name.lstrip("-")).lower()
        for name in search.get("objectives") or []
    ]
    first = (
        f"The search ran {budget.get('evaluations', search.get('evaluations'))} "
        f"simulations over {budget.get('generations', '-')} generations."
    )
    second = (
        f"{len(search['front'])} designs are on the trade-off front of "
        f"{joined(objectives)}."
        if objectives
        else f"{len(search['front'])} designs are on the trade-off front."
    )
    return sentences(first, second)


def related_reading(inputs: Inputs) -> str:
    """Name the project's sensitivity and uncertainty studies of the same plant (QA-338)."""
    if not inputs.related:
        return "No sensitivity or uncertainty study of this plant version is in the project."
    lines = []
    for study, result in inputs.related:
        run = (result.content.get("run") or {}) if result is not None else {}
        tornado = gemini_evaluate.tornado_of(run)
        spread = gemini_evaluate.spread_of(run)
        if tornado:
            top = tornado[0]
            lines.append(
                f"The sensitivity study {study.name} finds {top['parameter']} the largest "
                f"driver of {top['metric'].lower()} "
                f"({text({'value': top['effect'], 'unit': top['unit']})})."
            )
        elif spread:
            item = spread[0]
            lines.append(
                f"The uncertainty study {study.name} puts {item['metric'].lower()} between "
                f"{text({'value': item['p5'], 'unit': item['unit']})} and "
                f"{text({'value': item['p95'], 'unit': item['unit']})} (P5 to P95)."
            )
        else:
            lines.append(f"The project also has the study {study.name} ({study.kind}).")
    lines.append("Choose that study's result to show its full table.")
    return " ".join(lines)


def study_origin(study: Study | None) -> str | None:
    if study is None:
        return None
    titles = {item["kind"]: item["title"] for item in gemini_study.kinds()}
    kind = titles.get(study.kind, study.kind)
    objective = (study.settings or {}).get("objective")
    goal = (
        f", with the objective {gemini_evaluate.title_of(objective).lower()}"
        if isinstance(objective, str) and objective
        else ""
    )
    return f"The result comes from the study {study.name} (kind: {kind}){goal}."


def tornado_reading(rows: list[dict[str, Any]]) -> str:
    top = rows[0]
    first = (
        f"{top['parameter']} has the largest effect: moving it from {top['low']} to "
        f"{top['high']} changes {top['metric'].lower()} by "
        f"{text({'value': top['effect'], 'unit': top['unit']})}."
    )
    second = None
    if len(rows) > 1:
        other = rows[1]
        second = (
            f"Next is {other['parameter']} with "
            f"{text({'value': other['effect'], 'unit': other['unit']})}."
        )
    flips = [
        row["parameter"]
        for row in rows
        if row.get("feasible_low") is False or row.get("feasible_high") is False
    ]
    third = (
        f"At one end of {joined(sorted(set(flips)))} the design no longer meets every check."
        if flips
        else None
    )
    return sentences(first, second, third)


def spread_reading(rows: list[dict[str, Any]]) -> str:
    def width(row: dict[str, Any]) -> float:
        return abs(row["p95"] - row["p5"]) / abs(row["p50"]) if row["p50"] else 0.0

    widest = max(rows, key=width)
    first = (
        f"{widest['metric']} varies the most: from "
        f"{text({'value': widest['p5'], 'unit': widest['unit']})} to "
        f"{text({'value': widest['p95'], 'unit': widest['unit']})} between P5 and P95, "
        f"around a median of {text({'value': widest['p50'], 'unit': widest['unit']})}."
    )
    feasible, draws = rows[0]["feasible"], rows[0]["draws"]
    second = (
        f"{feasible} of the {draws} draws meet every check."
        if feasible is not None
        else None
    )
    return sentences(first, second)


def checks(inputs: Inputs, numbers: Numbers, rows: list[list[str]]) -> str:
    counts = inputs.result.summary["checks"]
    line = (
        f"{counts['passed']} passed, {counts['failed']} failed, "
        f"{counts['not_assessed']} not assessed."
    )
    if not rows:
        return line
    return block(
        line,
        table(["Check", "Status", "Value", "Limit", "Margin", "Worst day"], rows),
        numbers.table("Constraint checks of the design"),
        checks_reading(inputs),
        scope_reading(inputs),
    )


def checkable() -> list[str]:
    """Return the quantities a case rule can bound, from gemini's case schema."""
    items = (
        gemini_case.schema()
        .get("properties", {})
        .get("requirements", {})
        .get("items", {})
    )
    return list(items.get("properties", {}).get("quantity", {}).get("enum") or [])


def scope_reading(inputs: Inputs) -> str:
    """Say what the checks cover and what they do not, from gemini's rules (QA-325).

    "All checks pass" read as a full validation. The checks are only the case's rules, each on
    the simulated period; a quantity gemini can bound that the case names no rule for is not
    checked, nor anything over a longer time than the run.
    """
    rules = inputs.report.get("requirements") or []
    checked = sorted({item["quantity"] for item in rules if item.get("quantity")})
    roles = sorted({item["role"] for item in rules if item.get("role")})
    words = [name.replace("_", " ") for name in checked]
    first = (
        f"The checks are the {len(rules)} rules of the case. They bound "
        f"{joined(words)} on the {joined([role.replace('_', ' ') for role in roles])}."
        if checked
        else "The case states no rule, so nothing is checked."
    )
    known = checkable()
    left = [name.replace("_", " ") for name in known if name not in checked]
    second = (
        f"The engine can also bound {joined(left)}; the case sets no rule on "
        f"{'it' if len(left) == 1 else 'them'}, so they are not checked."
        if left
        else None
    )
    window = (inputs.report.get("co2") or {}).get("window")
    span = text(window) if shown(window) else "the simulated period"
    third = (
        f"Every check judges the run of {span} only: nothing that develops over a "
        "longer life of the plant is checked."
    )
    return sentences(first, second, third)


def checks_reading(inputs: Inputs) -> str:
    constraints = gemini_evaluate.summarise(inputs.report, inputs.limits)["constraints"]
    failed = [
        check_name(item)
        for item in constraints
        if item["status"] == gemini_evaluate.FAILED
    ]
    unknown = [
        f"{check_name(item)} ({item['message']})"
        for item in constraints
        if item["status"] == gemini_evaluate.NOT_ASSESSED
    ]
    first = (
        f"The design fails {joined(failed[:TOP_ITEMS])}."
        if failed
        else "No check fails."
    )
    second = (
        f"Not assessed: {joined(unknown[:TOP_ITEMS])}; a design with an unassessed check "
        "is not counted as feasible."
        if unknown
        else "Every check could be assessed."
    )
    return sentences(first, second)


def assumptions(inputs: Inputs, numbers: Numbers) -> str:
    result, case = inputs.result, inputs.case
    origin = inputs.economics.get("file")
    rows = [
        [
            "Case",
            "-"
            if case is None
            else f"{case.content.get('name') or 'case'}, version {case.number}",
            "Project case",
        ],
        [
            "Plant",
            "not a saved version"
            if result.plant_version is None
            else f"version {result.plant_version}",
            "Project plant" if result.plant_version is not None else "Study result",
        ],
        [
            "Economics",
            origin or ("in the case" if inputs.economics else "not given"),
            "Case file" if origin else ("Case" if inputs.economics else "-"),
        ],
    ]
    if case is not None:
        period = period_of(case.content.get("time") or {})
        if period:
            rows.append(["Simulation period", period, "Case"])
    prices = [
        [path_words(path), value_text(item), origin or "case economics"]
        for path, item in quantities(
            {key: value for key, value in inputs.economics.items() if key != "file"}
        )
    ]
    parts = [
        table(["Input", "Value", "Source"], rows),
        numbers.table("Inputs the result was computed from"),
        "Every figure of this report is computed by the engine from these inputs; a value "
        "the inputs do not give is reported as missing, never assumed.",
    ]
    if prices:
        uncertain = sum(
            1
            for _, item in quantities(inputs.economics)
            if isinstance(item.get("uncertainty"), dict)
        )
        parts += [
            table(["Economic value", "Amount", "Source"], prices),
            numbers.table("Economic values of the case"),
            sentences(
                f"The case states {len(prices)} economic values.",
                f"{uncertain} of them carry an uncertainty range."
                if uncertain
                else None,
            ),
        ]
    return block(*parts)
