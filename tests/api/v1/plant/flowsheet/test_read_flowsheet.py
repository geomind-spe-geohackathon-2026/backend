from uuid import uuid4

import gemini as gm

from tests.api.v1.plant.helpers import FLOWSHEET, first_module, save_plant
from tests.conftest import bearer
from tests.plants import changed_plant, example_plant


async def test_no_plant_is_plant_not_found(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.get(
        FLOWSHEET, params={"project": str(project.id)}, headers=bearer(owner)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "plant_not_found"


async def test_project_query_is_required_and_checked(
    client,
    make_user,
    blobs,
) -> None:
    owner = await make_user()

    missing = await client.get(FLOWSHEET, headers=bearer(owner))
    unknown = await client.get(
        FLOWSHEET, params={"project": str(uuid4())}, headers=bearer(owner)
    )

    assert missing.json()["error"]["code"] == "validation_failed"
    assert unknown.json()["error"]["code"] == "project_not_found"


async def test_layout_is_saved_without_a_new_version(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)
    layout = {first_module(): {"x": 10, "y": 20}}

    response = await client.put(
        f"{FLOWSHEET}/layout",
        headers=bearer(owner),
        json={"project": str(project.id), "base": 1, "layout": layout},
    )
    versions = await client.get(
        f"{FLOWSHEET}/versions",
        params={"project": str(project.id)},
        headers=bearer(owner),
    )

    assert response.status_code == 200
    assert response.json()["layout"] == layout
    assert response.json()["version"] == 1
    assert len(versions.json()["items"]) == 1


async def test_layout_with_a_stale_base_is_conflict(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)

    response = await client.put(
        f"{FLOWSHEET}/layout",
        headers=bearer(owner),
        json={"project": str(project.id), "base": 5, "layout": {}},
    )

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"latest": 1}


async def test_layout_without_a_plant_is_plant_not_found(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.put(
        f"{FLOWSHEET}/layout",
        headers=bearer(owner),
        json={"project": str(project.id), "base": None, "layout": {}},
    )

    assert response.json()["error"]["code"] == "plant_not_found"


async def test_versions_are_newest_first_with_author(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)
    await save_plant(client, bearer(owner), project, 1, changed_plant(2))

    response = await client.get(
        f"{FLOWSHEET}/versions",
        params={"project": str(project.id)},
        headers=bearer(owner),
    )

    body = response.json()
    assert [item["number"] for item in body["items"]] == [2, 1]
    assert body["next"] is None
    assert body["items"][0]["author"] == {"id": str(owner.id), "name": owner.name}
    assert body["items"][0]["note"] == "first"


async def test_an_old_version_is_read_by_number(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)
    await save_plant(client, bearer(owner), project, 1, changed_plant(2))

    first = await client.get(
        f"{FLOWSHEET}/versions/1",
        params={"project": str(project.id)},
        headers=bearer(owner),
    )
    missing = await client.get(
        f"{FLOWSHEET}/versions/9",
        params={"project": str(project.id)},
        headers=bearer(owner),
    )

    assert first.json()["spec"] == example_plant()
    assert missing.json()["error"]["code"] == "plant_not_found"


async def test_validate_lists_structural_problems(client, make_user, blobs) -> None:
    user = await make_user()
    spec = example_plant()
    spec["params"]["zz_unknown"] = {"value": 1}

    response = await client.post(
        f"{FLOWSHEET}/validate", headers=bearer(user), json={"spec": spec}
    )

    problems = response.json()["problems"]
    assert [problem["code"] for problem in problems] == ["unknown_name"]
    assert set(problems[0]) == {"path", "message", "code"}


async def test_validate_lists_missing_values_of_a_good_structure(
    client,
    make_user,
    blobs,
) -> None:
    user = await make_user()

    response = await client.post(
        f"{FLOWSHEET}/validate",
        headers=bearer(user),
        json={"spec": example_plant()},
    )

    problems = response.json()["problems"]
    assert problems
    assert {problem["code"] for problem in problems} == {"missing_value"}


async def test_validate_gives_warnings_beside_problems(
    client, make_user, blobs
) -> None:
    user = await make_user()
    response = await client.post(
        f"{FLOWSHEET}/validate", headers=bearer(user), json={"spec": example_plant()}
    )
    body = response.json()
    assert set(body) == {"problems", "warnings"}
    assert all(set(item) == {"path", "message", "code"} for item in body["warnings"])


async def test_suggest_names_the_ports_a_port_may_connect_to(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)
    path = f"{FLOWSHEET}/suggest"
    query = {"project": str(project.id), "port": "hx.cold_out", "limit": 2}

    response = await client.get(path, params=query, headers=bearer(owner))

    if not hasattr(gm.Plant, "suggest"):
        assert response.status_code == 501
        return
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["port"] == "hx.cold_out"
    assert len(body["suggestions"]) <= 2
    keys = {"port", "match", "exact", "loose", "closes_loop"}
    assert all(set(item) == keys for item in body["suggestions"])
