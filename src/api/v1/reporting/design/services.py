import json
import re
from dataclasses import dataclass
from typing import Any

from src.api.v1.reporting.design import (
    document,
    errors,
    figures,
    narrative,
    pdf,
    schemas,
)
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
from src.core.routes import REPORT_ROUTE
from src.core.security.access import require_project

SECTION_TITLES = {
    "summary": "1 Summary",
    "case": "2 Case and demand",
    "design": "3 Plant design",
    "coverage": "4 Performance",
    "costs": "5 Economics",
    "emissions": "6 Emissions",
    "findings": "7 Studies",
    "checks": "8 Checks",
    "assumptions": "9 Assumptions and sources",
    "agentlog": "Appendix A - Agent log and tokens",
    "appendix": "Appendix B - Modules and connections",
}
"""The report's sections in order (QA-313); the numbers are the section numbers."""
FOLDED = {"capacities": "design", "capex": "costs"}
"""Sections of earlier reports that are now part of a numbered one: a request naming one
gets the section that holds it."""
SECTION_NUMBERS = {
    key: int(title.split(" ", 1)[0])
    for key, title in SECTION_TITLES.items()
    if title[0].isdigit()
}
PAGE_BREAK = '<div style="page-break-before: always"></div>'
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
    return document.table(headers, rows)


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


def check_rows(inputs: document.Inputs) -> list[list[str]]:
    parts = gemini_evaluate.summarise(inputs.report, inputs.limits)
    return [check_row(item) for item in parts["constraints"]]


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


def appendix_markdown(result: Result) -> str:
    plant = gemini_evaluate.describe_plant(result.content["design"])
    parts = gemini_evaluate.summarise(result.content["report"])
    rows = rating_rows(parts["sizes"])
    sizes = table(["Module", "Kind", "Size", "Peak", "Used"], rows) if rows else ""
    return "\n\n".join(filter(None, [sizes, design_table(plant)]))


def token_count(count: int) -> str:
    """Write a token count as Runs and logs does: ``14.8 M``, ``625 K`` (QA-136)."""
    for size, unit in ((1_000_000, "M"), (1_000, "K")):
        if count >= size - size // 2000:
            return f"{count / size:.3g} {unit}"
    return str(count)


def agentlog_markdown(run: Run | None) -> str:
    if run is None:
        return "No assistant run was chosen."
    return "\n".join(
        [
            f"- Status: {run.status}",
            f"- Input tokens: {token_count(run.input_tokens)}",
            f"- Output tokens: {token_count(run.output_tokens)}",
            f"- Cost: {run.cost:.2f} USD",
        ]
    )


def section_markdown(key: str, inputs: document.Inputs) -> str:
    numbers = document.Numbers(SECTION_NUMBERS.get(key, 0))
    builders = {
        "summary": lambda: document.summary(inputs, numbers),
        "case": lambda: document.case_section(inputs, numbers),
        "design": lambda: document.design_section(inputs, numbers),
        "coverage": lambda: document.performance(inputs, numbers),
        "costs": lambda: document.economics(inputs, numbers),
        "emissions": lambda: document.emissions(inputs, numbers),
        "findings": lambda: document.studies(inputs, numbers),
        "checks": lambda: document.checks(inputs, numbers, check_rows(inputs)),
        "assumptions": lambda: document.assumptions(inputs, numbers),
        "appendix": lambda: appendix_markdown(inputs.result),
        "agentlog": lambda: agentlog_markdown(inputs.run),
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


async def related_studies(
    result: Result, repositories: Repositories
) -> list[tuple[Study, Result | None]]:
    """Return the project's sensitivity and uncertainty studies of the result's plant version.

    The Studies section names them beside an optimisation, with their main finding (QA-338).
    """
    if result.plant_version is None:
        return []
    found = []
    for study in await repositories.studies.all_for_project(result.project_id):
        if study.id == result.study_id or study.kind not in document.RELATED_KINDS:
            continue
        if study.plant_version != result.plant_version:
            continue
        found.append((study, await repositories.results.get_for_study(study.id)))
    return found


async def preview_report(
    request: schemas.ReportRequest,
    user: User,
    repositories: Repositories,
    blobs: BlobStore,
) -> schemas.Report:
    project, result, study, run = await load_inputs(request, user, repositories)
    wanted = {FOLDED.get(key, key) for key in request.include}
    case = None
    if result.case_version is not None:
        case = await repositories.cases.version_by_number(
            project.id, result.case_version
        )
    limits = gemini_evaluate.case_limits(None if case is None else case.content)
    economics = await economics_of(case, repositories, blobs)
    related = await related_studies(result, repositories)
    inputs = document.Inputs(result, study, run, case, limits, economics, related)
    sections = [
        schemas.ReportSection(
            key=key, title=title, markdown=section_markdown(key, inputs)
        )
        for key, title in SECTION_TITLES.items()
        if key in wanted
    ]
    return schemas.Report(
        title=f"{project.name}: {result.name}",
        sections=sections,
        flowsheet=gemini_plant.structure_of(result.content["design"]),
    )


def with_image(
    report: schemas.Report, svg: str | None, title: str, place: str
) -> schemas.Report:
    """Put a picture the page drew at the end of one section of an export."""
    if svg is None or not svg.startswith("<svg"):
        return report
    line = figures.image_line(svg, title)
    sections = [
        item.model_copy(update={"markdown": f"{item.markdown}\n\n{line}"})
        if item.key == place
        else item
        for item in report.sections
    ]
    return report.model_copy(update={"sections": sections})


def with_flowsheet(report: schemas.Report, svg: str | None) -> schemas.Report:
    """Put the process diagram where the Plant design section marks it, or drop the mark."""
    drawn = svg is not None and svg.startswith("<svg")
    line = figures.image_line(svg, "Flowsheet") if drawn else ""
    sections = [
        item.model_copy(
            update={
                "markdown": item.markdown.replace(document.FLOWSHEET_MARKER, line)
                .replace("\n\n\n\n", "\n\n")
                .strip()
            }
        )
        for item in report.sections
    ]
    return report.model_copy(update={"sections": sections})


def with_full_flowsheet(report: schemas.Report, svg: str | None) -> schemas.Report:
    """Put the flowsheet of every module in the appendix of an export."""
    return with_image(report, svg, "Detailed flowsheet", "appendix")


def to_markdown(report: schemas.Report) -> str:
    """Write the report as Markdown: each top-level section starts a new printed page."""
    parts = [f"# {report.title}"]
    for at, item in enumerate(report.sections):
        if at:
            parts.append(PAGE_BREAK)
        parts.append(f"## {item.title}\n\n{item.markdown}")
    return "\n\n".join(parts) + "\n"


async def export_report(
    request: schemas.ReportExport,
    user: User,
    repositories: Repositories,
    blobs: BlobStore,
) -> Export:
    report = await preview_report(request, user, repositories, blobs)
    shown = with_flowsheet(report, request.flowsheet_svg)
    markdown = to_markdown(with_full_flowsheet(shown, request.flowsheet_full_svg))
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
