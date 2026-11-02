import json
import re
from dataclasses import dataclass
from typing import Any

from src.api.v1.reporting.design import errors, figures, narrative, pdf, schemas
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.models.study import Study
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.gemini import evaluate as gemini_evaluate
from src.core.gemini import plant as gemini_plant
from src.core.gemini import study as gemini_study
from src.core.routes import REPORT_ROUTE
from src.core.security.access import require_project

SECTION_TITLES = {
    "summary": "Summary",
    "design": "Plant",
    "capacities": "Capacities",
    "coverage": "Days covered",
    "checks": "Constraint checks",
    "costs": "Costs",
    "findings": "Uncertainty and sensitivity",
    "agentlog": "Agent log and tokens",
    "appendix": "Appendix: modules and connections",
}
MEDIA_TYPES = {"md": "text/markdown", "pdf": "application/pdf"}


@dataclass(frozen=True, slots=True)
class Repositories:
    projects: ProjectRepository
    results: ResultRepository
    studies: StudyRepository
    runs: RunRepository
    activity: ActivityRepository
    cases: CaseVersionRepository
    files: CaseFileRepository


@dataclass(frozen=True, slots=True)
class Export:
    filename: str
    media_type: str
    content: bytes


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines += [
        "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |"
        for row in rows
    ]
    return "\n".join(lines)


def rating_rows(items: list[dict[str, Any]]) -> list[list[str]]:
    return [
        [
            narrative.module_words(item["title"]),
            item["kind"],
            narrative.figure_text(item),
            "-"
            if item["peak"] is None
            else narrative.figure_text(
                {"value": item["peak"], "unit": item["peak_unit"]}
            ),
            "-" if item["share"] is None else f"{item['share'] * 100:.0f}%",
        ]
        for item in items
    ]


def capacities_markdown(result: Result) -> str:
    parts = gemini_evaluate.summarise(result.content["report"])
    rows = rating_rows(parts["capacities"])
    headers = ["Module", "Kind", "Rated", "Peak", "Used"]
    return table(headers, rows) if rows else "No capacities."


def summary_markdown(result: Result) -> str:
    report = result.content["report"]
    parts = gemini_evaluate.summarise(report)
    coverage = result.content.get("coverage")
    sentences = narrative.summary_sentences(
        report, parts["capacities"], coverage, result.summary["checks"]
    )
    tiles = narrative.tiles_of(report, coverage)
    lead = " ".join(sentences)
    if not tiles:
        return lead
    return figures.image_line(figures.kpi_tiles(tiles), "Key figures") + "\n\n" + lead


def coverage_markdown(result: Result) -> str:
    coverage = result.content.get("coverage")
    if coverage is None:
        return "Made before daily coverage existed."
    rows = []
    charts = [figures.image_line(figures.day_strips(coverage), "Days covered")]
    for service, days in coverage.items():
        count = {name: 0 for name in ("geothermal", "backup", "short")}
        for day in days:
            count[day["source"]] += 1
        rows.append([service.capitalize(), *(str(value) for value in count.values())])
        if days:
            title = f"{service.capitalize()}: demand and supply"
            labels = (figures.source_word(service, "geothermal"), "Backup")
            chart = figures.supply_chart(title, days, labels)
            charts.append(figures.image_line(chart, title))
    days_table = table(["Service", "Geothermal or plant", "Backup", "Short"], rows)
    note = (
        "On cooling days the whole supply is the plant: gemini has no cooling backup."
    )
    return "\n\n".join([*charts, days_table, note])


def findings_markdown(result: Result) -> str:
    run = result.content.get("run", {})
    parts = []
    tornado = gemini_evaluate.tornado_of(run)
    if tornado:
        rows = [
            [
                item["parameter"],
                item["metric"],
                f"{item['low']} to {item['high']}",
                narrative.figure_text({"value": item["effect"], "unit": item["unit"]}),
            ]
            for item in tornado
        ]
        parts.append(table(["Value", "Metric", "Moved", "Effect"], rows))
    spread = gemini_evaluate.spread_of(run)
    if spread:
        rows = [
            [
                item["metric"],
                *(
                    narrative.figure_text({"value": item[key], "unit": item["unit"]})
                    for key in ("mean", "p5", "p95")
                ),
            ]
            for item in spread
        ]
        lead = f"Over {spread[0]['draws']} draws."
        parts.append(lead + "\n\n" + table(["Metric", "Mean", "P5", "P95"], rows))
    return (
        "\n\n".join(parts) or "This result is not a sensitivity or uncertainty study."
    )


def checks_markdown(result: Result, limits: dict[str, dict[str, Any]]) -> str:
    checks = result.summary["checks"]
    line = (
        f"{checks['passed']} passed, {checks['failed']} failed, "
        f"{checks['not_assessed']} not assessed."
    )
    parts = gemini_evaluate.summarise(result.content["report"], limits)
    rows = [check_row(item) for item in parts["constraints"]]
    headers = ["Check", "Status", "Value", "Limit", "Margin", "Worst day"]
    return line + "\n\n" + table(headers, rows) if rows else line


def check_row(item: dict[str, Any]) -> list[str]:
    value = item["message"]
    if item["value"] is not None:
        value = narrative.figure_text({"value": item["value"], "unit": item["unit"]})
    margin = "-"
    if item["margin"] is not None:
        margin = narrative.margin_text(item["margin"], item["unit"])
    return [
        module_title(item),
        item["status"],
        value,
        item["limit"],
        margin,
        item["worst"] or "-",
    ]


def module_title(item: dict[str, Any]) -> str:
    if not item["module"]:
        return item["title"]
    return f"{item['title']} ({narrative.module_words(item['module'])})"


def capex_markdown(result: Result, economics: dict[str, Any]) -> str:
    rows = narrative.capex_rows(result.content["report"], economics)
    if not rows:
        return ""
    headers = ["Item", "Amount", "Unit cost", "Source"]
    return f"### Capital cost by kind\n\n{table(headers, rows)}"


def costs_markdown(result: Result, economics: dict[str, Any]) -> str:
    source = (
        f"From case version {result.case_version}, "
        f"plant version {result.plant_version}."
    )
    groups = narrative.grouped_figures(result.content["report"])
    if not groups:
        return "No costs."
    tables = [
        f"### {name}\n\n{table(['Figure', 'Value'], rows)}"
        for name, rows in groups.items()
    ]
    capex = capex_markdown(result, economics)
    return "\n\n".join([source, *tables, *([capex] if capex else [])])


def design_table(summary: str) -> str:
    """Turn gemini's fixed-width module table into a Markdown table."""
    lines = summary.splitlines()
    header = next((line for line in lines if line.startswith("Module")), None)
    if header is None:
        return f"```\n{summary}\n```"
    names = re.findall(r"\S+(?: \S+)*", header)
    starts = [header.index(name) for name in names]
    bounds = [*starts, None]
    first = lines.index(header)

    def is_row(line: str) -> bool:
        return line[starts[1] - 1 : starts[1]] == " " and bool(line.strip())

    body = [line for line in lines[first + 1 :] if line.strip()]
    rows = [
        [line[bounds[i] : bounds[i + 1]].strip() for i in range(len(names))]
        for line in body
        if is_row(line)
    ]
    notes = [line for line in body if not is_row(line)]
    lead = [line for line in lines[:first] if line.strip()]
    return "\n\n".join([*lead, table(names, rows), *notes])


def design_markdown(result: Result, study: Study | None) -> str:
    kind = gemini_plant.type_of(result.content["design"])
    kind_title = "" if study is None else gemini_study.KIND_TITLES.get(study.kind, "")
    origin = f" from a study of kind {kind_title}" if kind_title else ""
    return f"Design {result.name}{origin}, plant type {narrative.spaced(kind)}."


def appendix_markdown(result: Result) -> str:
    plant = gemini_evaluate.describe_plant(result.content["design"])
    parts = gemini_evaluate.summarise(result.content["report"])
    rows = rating_rows(parts["sizes"])
    sizes = table(["Module", "Kind", "Size", "Peak", "Used"], rows) if rows else ""
    return "\n\n".join(filter(None, [sizes, design_table(plant)]))


def agentlog_markdown(run: Run | None) -> str:
    if run is None:
        return "No assistant run was chosen."
    return "\n".join(
        [
            f"- Status: {run.status}",
            f"- Input tokens: {run.input_tokens}",
            f"- Output tokens: {run.output_tokens}",
            f"- Cost: {run.cost}",
        ]
    )


def section_markdown(
    key: str,
    result: Result,
    study: Study | None,
    run: Run | None,
    limits: dict[str, dict[str, Any]],
    economics: dict[str, Any],
) -> str:
    builders = {
        "summary": lambda: summary_markdown(result),
        "capacities": lambda: capacities_markdown(result),
        "coverage": lambda: coverage_markdown(result),
        "findings": lambda: findings_markdown(result),
        "appendix": lambda: appendix_markdown(result),
        "design": lambda: design_markdown(result, study),
        "checks": lambda: checks_markdown(result, limits),
        "costs": lambda: costs_markdown(result, economics),
        "agentlog": lambda: agentlog_markdown(run),
    }
    return builders[key]()


def list_parts() -> list[schemas.ReportPart]:
    return [
        schemas.ReportPart(key=key, title=title)
        for key, title in SECTION_TITLES.items()
    ]


async def load_inputs(
    request: schemas.ReportRequest,
    user: User,
    repositories: Repositories,
) -> tuple[Project, Result, Study | None, Run | None]:
    project = await require_project(request.project, user, repositories.projects)
    result = await repositories.results.get_by_id(request.result)
    if result is None or result.project_id != project.id:
        raise errors.ResultNotFoundError("Result not found")
    study = None
    if result.study_id is not None:
        study = await repositories.studies.get_by_id(result.study_id)
    run = None
    if request.run is not None:
        run = await repositories.runs.get_by_id(request.run)
        if run is None or run.project_id != project.id:
            raise errors.RunNotFoundError("Run not found")
    return project, result, study, run


async def economics_of(
    case: CaseVersion | None,
    repositories: Repositories,
    blobs: BlobStore,
) -> dict[str, Any]:
    """Return the economics of a case, inline or from the file it names."""
    found = None if case is None else case.content.get("economics")
    if isinstance(found, dict):
        return {**found, "file": None}
    if not isinstance(found, str):
        return {}
    row = await repositories.files.get(case.id, found)
    data = None if row is None else await blobs.get(row.object_key)
    return {} if data is None else {**json.loads(data), "file": found}


async def preview_report(
    request: schemas.ReportRequest,
    user: User,
    repositories: Repositories,
    blobs: BlobStore,
) -> schemas.Report:
    project, result, study, run = await load_inputs(request, user, repositories)
    wanted = set(request.include)
    case = None
    if result.case_version is not None:
        case = await repositories.cases.version_by_number(
            project.id, result.case_version
        )
    limits = gemini_evaluate.case_limits(None if case is None else case.content)
    economics = await economics_of(case, repositories, blobs)
    sections = [
        schemas.ReportSection(
            key=key,
            title=title,
            markdown=section_markdown(key, result, study, run, limits, economics),
        )
        for key, title in SECTION_TITLES.items()
        if key in wanted
    ]
    return schemas.Report(
        title=f"{project.name}: {result.name}",
        sections=sections,
        flowsheet=gemini_plant.structure_of(result.content["design"]),
    )


def with_flowsheet(report: schemas.Report, svg: str | None) -> schemas.Report:
    """Put the picture the page drew under the Plant section of an export."""
    if svg is None or not svg.startswith("<svg"):
        return report
    line = figures.image_line(svg, "Flowsheet")
    keys = [item.key for item in report.sections]
    place = "capacities" if "capacities" in keys else "design"
    sections = [
        item.model_copy(update={"markdown": f"{item.markdown}\n\n{line}"})
        if item.key == place
        else item
        for item in report.sections
    ]
    return report.model_copy(update={"sections": sections})


def to_markdown(report: schemas.Report) -> str:
    parts = [f"# {report.title}"]
    parts += [f"## {item.title}\n\n{item.markdown}" for item in report.sections]
    return "\n\n".join(parts) + "\n"


async def export_report(
    request: schemas.ReportExport,
    user: User,
    repositories: Repositories,
    blobs: BlobStore,
) -> Export:
    report = await preview_report(request, user, repositories, blobs)
    markdown = to_markdown(with_flowsheet(report, request.flowsheet_svg))
    content = markdown.encode() if request.format == "md" else pdf.to_pdf(markdown)
    await repositories.activity.add(
        request.project,
        "user",
        user.name,
        f"Exported the report of {report.title} as {request.format}",
        REPORT_ROUTE,
    )
    return Export(
        f"report-{request.result}.{request.format}",
        MEDIA_TYPES[request.format],
        content,
    )
