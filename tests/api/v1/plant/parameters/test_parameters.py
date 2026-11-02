import json
from pathlib import Path

import gemini as gm

from tests.api.v1.plant.helpers import PARAMETERS, save_plant
from tests.conftest import bearer
from tests.plants import example_plant

EXAMPLE = Path(__file__).parents[4] / "fixtures" / "hackathon"
MODULE = "heat_exchanger"
QUANTITY = {"thermal_conductance": {"value": 5, "unit": "W/K"}}


def changed_range_plant() -> dict:
    return json.loads((EXAMPLE / "seed_plant.json").read_text())


def project_query(project, **extra) -> dict:
    return {"project": str(project.id), "module": MODULE, **extra}


async def test_parameters_show_schema_with_units_and_missing(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)

    response = await client.get(
        PARAMETERS, params=project_query(project), headers=bearer(owner)
    )

    body = response.json()
    assert response.status_code == 200
    assert body["module"] == MODULE
    assert body["type"] == "HeatExchanger"
    assert body["schema"]["properties"]["thermal_conductance"]["unit"] == "W/K"
    assert "thermal_conductance" in body["missing"]
    assert body["history"] == [
        {"valid_from": None, "params": body["history"][0]["params"]}
    ]


async def test_unknown_module_is_module_not_found(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)

    response = await client.get(
        PARAMETERS,
        params={"project": str(project.id), "module": "zz"},
        headers=bearer(owner),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "module_not_found"


async def test_parameters_without_a_plant_are_plant_not_found(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.get(
        PARAMETERS, params=project_query(project), headers=bearer(owner)
    )

    assert response.json()["error"]["code"] == "plant_not_found"


async def test_setting_parameters_makes_a_new_version(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)

    response = await client.post(
        PARAMETERS,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": 1,
            "module": MODULE,
            "params": QUANTITY,
            "note": "set",
        },
    )
    read = await client.get(
        PARAMETERS, params=project_query(project), headers=bearer(owner)
    )

    assert response.status_code == 201
    assert response.json()["number"] == 2
    assert read.json()["values"]["thermal_conductance"] == 5
    assert "thermal_conductance" not in read.json()["missing"]


async def test_dated_values_are_read_at_a_time(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)
    for base, value, valid_from in ((1, 5, None), (2, 7, "2030-01-01T00:00:00Z")):
        await client.post(
            PARAMETERS,
            headers=bearer(owner),
            json={
                "project": str(project.id),
                "base": base,
                "module": MODULE,
                "params": {"thermal_conductance": {"value": value, "unit": "W/K"}},
                "valid_from": valid_from,
                "note": "set",
            },
        )

    early = await client.get(
        PARAMETERS,
        params=project_query(project, at="2029-01-01T00:00:00Z"),
        headers=bearer(owner),
    )
    latest = await client.get(
        PARAMETERS, params=project_query(project), headers=bearer(owner)
    )

    assert early.json()["values"]["thermal_conductance"] == 5
    assert latest.json()["values"]["thermal_conductance"] == 7
    assert len(latest.json()["history"]) == 2


async def test_wrong_unit_is_plant_invalid(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)

    response = await client.post(
        PARAMETERS,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": 1,
            "module": MODULE,
            "params": {"thermal_conductance": {"value": 5, "unit": "m"}},
            "note": "bad",
        },
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "plant_invalid"
    assert error["details"]["problems"][0]["code"] == "invalid_unit"


async def test_parameters_with_a_stale_base_are_conflict(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project)

    response = await client.post(
        PARAMETERS,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": 4,
            "module": MODULE,
            "params": QUANTITY,
            "note": "x",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"latest": 1}


async def test_fill_is_not_implemented_until_the_catalogue_exists(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.post(
        f"{PARAMETERS}/fill",
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": None,
            "module": MODULE,
            "entry": "e1",
            "note": "x",
        },
    )

    assert response.status_code == 501
    assert response.json()["error"] == {
        "code": "not_implemented",
        "message": "This is not available yet",
        "details": {"missing": "plant.catalogue"},
    }


def test_saved_spec_keeps_what_gemini_wrote() -> None:
    assert gm.Plant.from_dict(example_plant()).to_dict() == example_plant()


async def test_a_range_is_saved_shown_and_removed(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    headers = bearer(owner)
    spec = changed_range_plant()
    await save_plant(client, headers, project, spec=spec)
    query = {"project": str(project.id), "module": "d0"}

    async def save(base: int, limits: dict) -> None:
        body = {
            "project": str(project.id),
            "base": base,
            "module": "d0",
            "params": {},
            "ranges": {"nominal_flow": limits},
            "note": "range",
        }
        response = await client.post(PARAMETERS, json=body, headers=headers)
        assert response.status_code == 201, response.text

    await save(1, {"min": 60, "max": 200})
    shown = (await client.get(PARAMETERS, params=query, headers=headers)).json()
    assert "nominal_flow" in shown["ranges"]
    assert shown["search"]["nominal_flow"]["min"] == 60
    assert shown["search"]["nominal_flow"]["max"] == 200

    await save(2, {"min": None, "max": None})
    shown = (await client.get(PARAMETERS, params=query, headers=headers)).json()
    assert shown["search"]["nominal_flow"]["min"] is None


async def test_gemini_words_a_range_it_refuses(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_plant(client, bearer(owner), project, spec=changed_range_plant())

    response = await client.post(
        PARAMETERS,
        json={
            "project": str(project.id),
            "base": 1,
            "module": "d0",
            "params": {},
            "ranges": {"nominal_flow": {"min": 300, "max": 50}},
            "note": "range",
        },
        headers=bearer(owner),
    )

    assert response.status_code == 422
    assert "above max" in response.text
