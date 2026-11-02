import copy
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.gemini import evaluate
from tests import design_inputs
from tests.conftest import bearer

URL = "/api/v1/design/results"


def outcome_with(lcts: float, co2: float, feasible: bool = True) -> dict[str, Any]:
    outcome = copy.deepcopy(design_inputs.outcome())
    report = outcome["report"]
    report["lcts"]["value"] = lcts
    report["co2"]["value"] = co2
    report["verdict"] = {"feasible": feasible, "reasons": [] if feasible else [{}]}
    return outcome


@pytest.fixture
def make_result(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[Result]]:
    async def create(project: Project, name: str, outcome: dict[str, Any]) -> Result:
        parts = evaluate.summarise(outcome["report"])
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
                    "name": name,
                    "case_version": 1,
                    "plant_version": 2,
                    "summary": parts["summary"],
                    "content": content,
                }
            )

    return create


async def test_list_gives_summaries(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project, "A", outcome_with(40, 10))

    response = await client.get(f"{URL}?project={project.id}", headers=bearer(user))

    item = response.json()["items"][0]
    assert item["id"] == str(result.id)
    assert item["checks"] == {"passed": 13, "failed": 0, "not_assessed": 2}
    assert item["study"] is None
    assert {"name": "lcts", "title": "lcts", "value": 40, "unit": "EUR/MWh"} in item[
        "kpis"
    ]


async def test_detail_passes_gemini_content_through(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project, "A", outcome_with(40, 10))

    response = await client.get(f"{URL}/{result.id}", headers=bearer(user))

    body = response.json()
    assert body["coverage"] is None
    assert body["series"] == []
    assert body["capacities"][0]["unit"] == "m3/h"
    statuses = {item["status"] for item in body["constraints"]}
    assert statuses == {"pass", "not_assessed"}


async def test_detail_of_a_stranger_is_not_found(
    client, make_user, make_project, make_result
) -> None:
    owner = await make_user()
    stranger = await make_user("stranger@example.com")
    result = await make_result(await make_project(owner), "A", outcome_with(40, 10))

    response = await client.get(f"{URL}/{result.id}", headers=bearer(stranger))

    assert response.json()["error"]["code"] == "result_not_found"


async def test_compare_maps_pareto_flags_to_ids(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    cheap = await make_result(project, "cheap", outcome_with(40, 20))
    clean = await make_result(project, "clean", outcome_with(60, 5))
    worse = await make_result(project, "worse", outcome_with(70, 25))
    ids = ",".join(str(item.id) for item in (cheap, clean, worse))

    response = await client.get(
        f"{URL}/compare?project={project.id}&ids={ids}&x=lcts&y=co2",
        headers=bearer(user),
    )

    body = response.json()
    assert [item["name"] for item in body["items"]] == ["cheap", "clean", "worse"]
    assert body["pareto"] == [str(cheap.id), str(clean.id)]


async def test_compare_leaves_out_infeasible_designs(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    best = await make_result(project, "best", outcome_with(40, 20))
    broken = await make_result(project, "broken", outcome_with(10, 1, False))
    ids = f"{best.id},{broken.id}"

    response = await client.get(
        f"{URL}/compare?project={project.id}&ids={ids}&x=lcts&y=co2",
        headers=bearer(user),
    )

    assert response.json()["pareto"] == [str(best.id)]


async def test_compare_refuses_an_unknown_figure(
    client, make_user, make_project, make_result
) -> None:
    user = await make_user()
    project = await make_project(user)
    result = await make_result(project, "A", outcome_with(40, 10))

    response = await client.get(
        f"{URL}/compare?project={project.id}&ids={result.id}&x=nope&y=co2",
        headers=bearer(user),
    )

    assert response.status_code == 422
    assert "x" in response.json()["error"]["details"]["fields"]


async def test_compare_refuses_bad_and_unknown_ids(
    client, make_user, make_project
) -> None:
    user = await make_user()
    project = await make_project(user)
    query = f"project={project.id}&x=lcts&y=co2"

    bad = await client.get(f"{URL}/compare?{query}&ids=zzz", headers=bearer(user))
    unknown = await client.get(
        f"{URL}/compare?{query}&ids=00000000-0000-0000-0000-000000000000",
        headers=bearer(user),
    )

    assert bad.json()["error"]["code"] == "validation_failed"
    assert unknown.json()["error"]["code"] == "result_not_found"
