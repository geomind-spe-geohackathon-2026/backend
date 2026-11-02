import gemini as gm

from tests.api.v1.plant.helpers import FLOWSHEET, save_plant
from tests.conftest import bearer
from tests.plants import example_plant


async def test_flowsheet_gives_the_free_structure_of_a_template_plant(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    saved = await save_plant(client, bearer(owner), project)

    structure = saved["structure"]
    assert "type" in saved["spec"]
    assert "type" not in structure
    assert "size" not in structure
    assert set(structure["modules"]) >= {"d0", "heat_exchanger"}
    assert len(structure["connections"]) == len(saved["connections"])
    assert gm.Plant.from_dict(structure).to_dict() == structure


async def test_an_edited_structure_validates_without_the_class_conflict(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    saved = await save_plant(client, bearer(owner), project)
    structure = saved["structure"]
    structure["modules"]["extra_pipe"] = {"type": "Pipe"}

    unwired = await client.post(
        f"{FLOWSHEET}/validate", headers=bearer(owner), json={"spec": structure}
    )
    structure.setdefault("inlets", {})["extra_fluid"] = "extra_pipe.fluid_in"
    structure["inlets"]["extra_air"] = "extra_pipe.air_in"
    structure.setdefault("outlets", {})["extra_out"] = "extra_pipe.fluid_out"
    structure["outlets"]["extra_loss"] = "extra_pipe.loss_out"
    response = await client.post(
        f"{FLOWSHEET}/validate", headers=bearer(owner), json={"spec": structure}
    )
    created = await client.post(
        FLOWSHEET,
        headers=bearer(owner),
        json={
            "project": str(project.id),
            "base": 1,
            "note": "pipe",
            "spec": structure,
        },
    )

    assert {problem["code"] for problem in unwired.json()["problems"]} == {
        "unconnected_port"
    }
    assert response.status_code == 200
    assert "unconnected_port" not in {
        problem["code"] for problem in response.json()["problems"]
    }
    assert created.status_code == 201, created.text
    assert "extra_pipe" in {item["id"] for item in created.json()["modules"]}
    assert "type" not in created.json()["spec"]


async def test_the_type_with_changed_modules_is_still_refused(
    client,
    make_user,
    blobs,
) -> None:
    owner = await make_user()
    spec = example_plant()
    spec["modules"] = {"only": {"type": "Pipe"}}

    response = await client.post(
        f"{FLOWSHEET}/validate", headers=bearer(owner), json={"spec": spec}
    )

    assert response.json()["problems"]
