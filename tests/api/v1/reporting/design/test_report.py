from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest

from src.api.v1.reporting.design import services
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.chat import ChatRepository
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.gemini import evaluate
from tests import design_inputs
from tests.conftest import bearer
from tests.routes import route_exists

PREVIEW = "/api/v1/reporting/design/preview"
EXPORT = "/api/v1/reporting/design/export"
INCLUDE = [
    "summary",
    "capacities",
    "design",
    "coverage",
    "checks",
    "costs",
    "findings",
    "agentlog",
    "appendix",
]


@pytest.fixture
def make_result(session_factory) -> Callable[..., Awaitable[Result]]:
    async def create(project: Project) -> Result:
        outcome = design_inputs.outcome()
        parts = evaluate.summarise(outcome["report"])
        outcome["report"]["opex"]["value"] = None
        outcome["report"]["opex"]["reason"] = "no price"
        content = {
            "capacities": parts["capacities"],
            "constraints": parts["constraints"],
            "coverage": None,
            "series": [],
            **outcome,
        }
        async with session_factory() as session:
            return await ResultRepository(session).create(
                {
                    "project_id": project.id,
                    "name": "Base",
                    "case_version": 3,
                    "plant_version": 4,
                    "summary": parts["summary"],
                    "content": content,
                }
            )

    return create


def body(project: Project, target: Result, **changes: Any) -> dict[str, Any]:
    base = {"project": str(project.id), "result": str(target.id), "include": INCLUDE}
    return {**base, **changes}


async def test_preview_has_the_chosen_sections_in_order(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project)

    response = await client.post(
        PREVIEW,
        json=body(project, result, include=["costs", "capacities"]),
        headers=bearer(user),
    )

    report = response.json()
    assert report["title"] == "Doublet: Base"
    assert [item["key"] for item in report["sections"]] == ["design", "costs"]
    assert report["sections"][0]["title"] == "3 Plant design"


async def test_costs_show_source_and_missing(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project)

    response = await client.post(
        PREVIEW, json=body(project, result), headers=bearer(user)
    )

    sections = {item["key"]: item["markdown"] for item in response.json()["sections"]}
    assert "case version 3, plant version 4" in sections["costs"]
    assert "| Operating cost | missing: no price |" in sections["costs"]
    assert "No assistant run was chosen." in sections["agentlog"]
    assert "plant type Heating plant" in sections["design"]
    assert "13 passed" in sections["checks"]


async def test_costs_list_the_figures_of_the_report_not_a_fixed_list(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project)

    response = await client.post(
        PREVIEW, json=body(project, result, include=["costs"]), headers=bearer(user)
    )

    costs = response.json()["sections"][0]["markdown"]
    assert "| Investment |" in costs
    assert "*Table 5.1 - Cost figures of the design*" in costs


async def test_design_is_a_table_with_the_columns_of_the_summary(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project)

    response = await client.post(
        PREVIEW, json=body(project, result, include=["appendix"]), headers=bearer(user)
    )

    design = response.json()["sections"][0]["markdown"]
    assert "| Module | Type | Category | Connected to | Parameters |" in design
    assert "| gas_grid | GasGrid | grids |  | 1 |" in design
    assert "```" not in design


async def test_checks_read_cleanly(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project)

    response = await client.post(
        PREVIEW, json=body(project, result, include=["checks"]), headers=bearer(user)
    )

    checks = response.json()["sections"][0]["markdown"]
    assert "| Pump efficiency (d0) | pass | 70\u2009% | 70 % |" in checks
    assert "*Table 8.1 - Constraint checks of the design*" in checks
    assert "Doublet count |" in checks
    assert "T00:00" not in checks


async def test_agent_log_describes_the_chosen_run(
    client, make_user, make_project, make_result, session_factory
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project)
    async with session_factory() as session:
        chat = await ChatRepository(session).create(project.id, "Chat", user.id)
        run = await RunRepository(session).create(uuid4(), chat.id, project.id, user.id)

    response = await client.post(
        PREVIEW,
        json=body(project, result, run=str(run.id), include=["agentlog"]),
        headers=bearer(user),
    )

    assert "Status: queued" in response.json()["sections"][0]["markdown"]
    assert "Cost: 0.00 USD" in response.json()["sections"][0]["markdown"]


def test_token_counts_read_like_runs_and_logs() -> None:
    assert services.token_count(14_837_406) == "14.8 M"
    assert services.token_count(625_009) == "625 K"
    assert services.token_count(1_500) == "1.5 K"
    assert services.token_count(999_700) == "1 M"
    assert services.token_count(312) == "312"


async def test_unknown_result_and_run_are_not_found(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project)
    nothing = "00000000-0000-0000-0000-000000000000"

    no_result = await client.post(
        PREVIEW, json=body(project, result, result=nothing), headers=bearer(user)
    )
    no_run = await client.post(
        PREVIEW, json=body(project, result, run=nothing), headers=bearer(user)
    )

    assert no_result.json()["error"]["code"] == "result_not_found"
    assert no_run.json()["error"]["code"] == "run_not_found"


async def test_export_markdown_records_a_report_activity(
    client, make_user, make_project, make_result, session
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project)

    response = await client.post(
        EXPORT, json=body(project, result, format="md"), headers=bearer(user)
    )

    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.startswith("# Doublet: Base\n\n## 1 Summary")
    assert services.PAGE_BREAK in response.text
    assert "<!-- flowsheet -->" not in response.text
    rows = await ActivityRepository(session).latest(project.id, 1)
    assert (rows[0].link_route, rows[0].link_id) == ("design/report", None)
    assert route_exists(rows[0].link_route, rows[0].link_id)


async def test_export_pdf(client, make_user, make_project, make_result) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project)

    response = await client.post(
        EXPORT, json=body(project, result, format="pdf"), headers=bearer(user)
    )

    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


async def test_parts_list_the_sections_with_their_titles_in_order(
    client, make_user
) -> None:
    user = await make_user()

    response = await client.get(f"{PREVIEW[:-8]}/parts", headers=bearer(user))

    assert response.status_code == 200
    assert response.json() == [
        {"key": "summary", "title": "1 Summary"},
        {"key": "case", "title": "2 Case and demand"},
        {"key": "design", "title": "3 Plant design"},
        {"key": "coverage", "title": "4 Performance"},
        {"key": "costs", "title": "5 Economics"},
        {"key": "emissions", "title": "6 Emissions"},
        {"key": "findings", "title": "7 Studies"},
        {"key": "checks", "title": "8 Checks"},
        {"key": "assumptions", "title": "9 Assumptions and sources"},
        {"key": "agentlog", "title": "Appendix A - Agent log and tokens"},
        {"key": "appendix", "title": "Appendix B - Modules and connections"},
    ]
