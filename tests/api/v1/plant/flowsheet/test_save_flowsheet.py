from copy import deepcopy

from tests.api.v1.plant.helpers import (
    FLOWSHEET,
    first_module,
    save_plant,
    template_name,
)
from tests.conftest import bearer
from tests.plants import changed_plant, example_plant
from tests.routes import route_exists


async def test_save_and_read_back_the_spec_unchanged(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    saved = await save_plant(client, bearer(owner), project)
    read = await client.get(
        FLOWSHEET, params={"project": str(project.id)}, headers=bearer(owner)
    )

    assert saved["version"] == 1
    assert read.json() == saved
    assert saved["spec"] == example_plant()
    assert saved["layout"] == {}


async def test_flowsheet_has_modules_and_connections_with_streams(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    saved = await save_plant(client, bearer(owner), project)

    modules = {module["id"]: module for module in saved["modules"]}
    assert all(module["category"] and module["title"] for module in modules.values())
    assert saved["connections"]
    for connection in saved["connections"]:
        assert connection["source"].rpartition(".")[0] in modules
        assert connection["target"].rpartition(".")[0] in modules
    assert any(connection["stream"] for connection in saved["connections"])


async def test_save_from_a_template_with_parameters(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.post(
        FLOWSHEET,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": None,
            "note": "from template",
            "template": template_name(),
            "parameters": {"heat_exchanger": {"arrangement": "parallel"}},
        },
    )

    assert response.status_code == 201
    params = response.json()["spec"]["params"]
    assert params["heat_exchanger"]["arrangement"]["value"] == "parallel"


async def test_save_needs_spec_or_template_not_both(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    body = {"project": str(project.id), "base": None, "note": "x"}

    neither = await client.post(FLOWSHEET, headers=bearer(owner), json=body)
    both = await client.post(
        FLOWSHEET,
        headers=bearer(owner),
        json={**body, "spec": example_plant(), "template": template_name()},
    )

    assert neither.status_code == both.status_code == 422
    assert neither.json()["error"]["code"] == "validation_failed"


async def test_invalid_spec_is_plant_invalid_with_gemini_problems(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    spec = deepcopy(example_plant())
    spec["params"]["zz_unknown"] = {"value": 1}

    response = await client.post(
        FLOWSHEET,
        headers=bearer(owner),
        json={"project": str(project.id), "base": None, "note": "x", "spec": spec},
    )

    error = response.json()["error"]
    assert response.status_code == 422
    assert error["code"] == "plant_invalid"
    problem = error["details"]["problems"][0]
    assert problem["code"] == "unknown_name"
    assert problem["path"].endswith("zz_unknown")


async def test_unknown_template_is_plant_invalid(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.post(
        FLOWSHEET,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": None,
            "note": "x",
            "template": "Nope",
        },
    )

    assert response.json()["error"]["code"] == "plant_invalid"


async def test_unknown_module_in_parameters_is_module_not_found(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.post(
        FLOWSHEET,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": None,
            "note": "x",
            "template": template_name(),
            "parameters": {"zz": {"a": 1}},
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "module_not_found"


async def test_stale_base_is_conflict_with_latest(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)

    response = await client.post(
        FLOWSHEET,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": None,
            "note": "again",
            "spec": changed_plant(2),
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"latest": 1}


async def test_identical_content_is_conflict(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)

    response = await client.post(
        FLOWSHEET,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": 1,
            "note": "same",
            "spec": example_plant(),
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_second_version_and_layout_with_it(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)

    response = await client.post(
        FLOWSHEET,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": 1,
            "note": "two",
            "spec": changed_plant(2),
            "layout": {first_module(): {"x": 1, "y": 2}},
        },
    )

    assert response.status_code == 201
    assert response.json()["version"] == 2
    assert response.json()["layout"] == {first_module(): {"x": 1, "y": 2}}


async def test_other_member_cannot_save(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    project = await make_project(owner)

    response = await client.post(
        FLOWSHEET,
        headers=bearer(other),
        json={
            "project": str(project.id),
            "base": None,
            "note": "x",
            "spec": example_plant(),
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


async def test_save_writes_an_activity_row(
    client,
    make_user,
    make_project,
    blobs,
    session,
) -> None:
    from src.core.clients.postgres.repositories.activity import ActivityRepository

    owner = await make_user()
    project = await make_project(owner)

    await save_plant(client, bearer(owner), project)

    rows = await ActivityRepository(session).latest(project.id, 10)
    assert [row.text for row in rows] == ["Saved plant version 1"]
    assert rows[0].link_route == "design/plant"
    assert route_exists(rows[0].link_route, rows[0].link_id)
