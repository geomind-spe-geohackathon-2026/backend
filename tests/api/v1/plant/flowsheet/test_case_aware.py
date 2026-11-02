import gemini as gm

from tests.api.v1.design.case.test_case import save_case, upload
from tests.api.v1.plant.helpers import FLOWSHEET, PARAMETERS, save_plant
from tests.cases import site_case
from tests.conftest import bearer


def doublet_structure() -> dict:
    return gm.plants.get("Doublet").to_dict(structure=True)


async def test_validate_with_a_project_takes_the_values_from_its_case(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    headers = bearer(owner)
    spec = doublet_structure()
    alone = await client.post(
        f"{FLOWSHEET}/validate", headers=headers, json={"spec": spec}
    )
    await save_case(client, headers, project, content=site_case())
    await upload(client, headers, project, 1)

    with_case = await client.post(
        f"{FLOWSHEET}/validate",
        headers=headers,
        json={"spec": spec, "project": str(project.id)},
    )

    before = {problem["path"] for problem in alone.json()["problems"]}
    after = {problem["path"] for problem in with_case.json()["problems"]}
    assert "params.drainage_radius" in before
    assert "params.drainage_radius" not in after
    assert len(after) < len(before)


async def test_parameters_missing_takes_the_case_into_account(
    client,
    make_user,
    make_project,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    headers = bearer(owner)
    await save_plant(client, headers, project, spec=doublet_structure())
    query = {"project": str(project.id), "module": "esp"}
    alone = await client.get(PARAMETERS, params=query, headers=headers)
    await save_case(client, headers, project, content=site_case())
    await upload(client, headers, project, 1)

    with_case = await client.get(PARAMETERS, params=query, headers=headers)

    assert alone.json()["missing"]
    assert len(with_case.json()["missing"]) < len(alone.json()["missing"])
