from dataclasses import dataclass

from src.api.v1.reporting.design import errors, pdf, schemas
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.models.study import Study
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.gemini import evaluate as gemini_evaluate
from src.core.security.access import require_project

REPORT_ROUTE = "report"
SECTION_TITLES = {
    "capacities": "Capacities",
    "design": "Design",
    "checks": "Checks",
    "costs": "Costs",
    "agentlog": "Agent log",
}
COST_NAMES = ("capex", "opex", "lcts", "lcoh", "lcoc")
MEDIA_TYPES = {"md": "text/markdown", "pdf": "application/pdf"}


@dataclass(frozen=True, slots=True)
class Repositories:
    projects: ProjectRepository
    results: ResultRepository
    studies: StudyRepository
    runs: RunRepository
    activity: ActivityRepository


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


def capacities_markdown(result: Result) -> str:
    rows = [
        [item["title"], gemini_evaluate.amount(item)]
        for item in result.content["capacities"]
    ]
    return table(["Module", "Capacity"], rows) if rows else "No capacities."


def checks_markdown(result: Result) -> str:
    checks = result.summary["checks"]
    line = (
        f"{checks['passed']} passed, {checks['failed']} failed, "
        f"{checks['not_assessed']} not assessed."
    )
    rows = [
        [item["title"], item["status"], item["message"]]
        for item in result.content["constraints"]
    ]
    return line + "\n\n" + table(["Check", "Status", "Detail"], rows) if rows else line


def costs_markdown(result: Result) -> str:
    source = f"case version {result.case_version}, plant version {result.plant_version}"
    report = result.content["report"]
    rows = []
    for name in COST_NAMES:
        item = report.get(name)
        if item is None:
            continue
        found = item["value"] is not None
        rows.append(
            [
                gemini_evaluate.title_of(name),
                gemini_evaluate.amount(item),
                source if found else "missing",
            ]
        )
    return table(["Figure", "Value", "Source"], rows) if rows else "No costs."


def design_markdown(result: Result, study: Study | None) -> str:
    lines = [f"Result: {result.name}."]
    if study is not None:
        lines.append(f"Study: {study.name} ({study.kind}).")
        settings = [f"- {key}: {value}" for key, value in study.settings.items()]
        lines += ["", "Settings:", *(settings or ["- none"])]
    plant = gemini_evaluate.describe_plant(result.content["design"])
    return "\n".join(lines) + f"\n\n```\n{plant}\n```"


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
) -> str:
    builders = {
        "capacities": lambda: capacities_markdown(result),
        "design": lambda: design_markdown(result, study),
        "checks": lambda: checks_markdown(result),
        "costs": lambda: costs_markdown(result),
        "agentlog": lambda: agentlog_markdown(run),
    }
    return builders[key]()


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


async def preview_report(
    request: schemas.ReportRequest,
    user: User,
    repositories: Repositories,
) -> schemas.Report:
    project, result, study, run = await load_inputs(request, user, repositories)
    wanted = set(request.include)
    sections = [
        schemas.ReportSection(
            key=key,
            title=title,
            markdown=section_markdown(key, result, study, run),
        )
        for key, title in SECTION_TITLES.items()
        if key in wanted
    ]
    return schemas.Report(title=f"{project.name}: {result.name}", sections=sections)


def to_markdown(report: schemas.Report) -> str:
    parts = [f"# {report.title}"]
    parts += [f"## {item.title}\n\n{item.markdown}" for item in report.sections]
    return "\n\n".join(parts) + "\n"


async def export_report(
    request: schemas.ReportExport,
    user: User,
    repositories: Repositories,
) -> Export:
    report = await preview_report(request, user, repositories)
    markdown = to_markdown(report)
    content = markdown.encode() if request.format == "md" else pdf.to_pdf(markdown)
    await repositories.activity.add(
        request.project,
        "user",
        user.name,
        f"Exported the report of {report.title} as {request.format}",
        REPORT_ROUTE,
        str(request.result),
    )
    return Export(
        f"report-{request.result}.{request.format}",
        MEDIA_TYPES[request.format],
        content,
    )
