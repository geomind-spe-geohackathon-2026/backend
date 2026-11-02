from uuid import uuid4

from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from tests.cases import DEMAND_CSV, DEMAND_FILE, example_case
from tests.conftest import bearer
from tests.plants import example_plant

PROJECTS = "/api/v1/workspace/projects"


async def test_owner_gets_project(client, make_user, make_project) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.get(f"{PROJECTS}/{project.id}", headers=bearer(owner))

    assert response.status_code == 200
    assert response.json()["id"] == str(project.id)


async def test_other_member_sees_the_same_answer_as_a_missing_project(
    client,
    make_user,
    make_project,
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    project = await make_project(owner)
    headers = bearer(other)

    hidden = await client.get(f"{PROJECTS}/{project.id}", headers=headers)
    missing = await client.get(f"{PROJECTS}/{uuid4()}", headers=headers)

    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    assert hidden.json()["error"]["code"] == "project_not_found"


async def test_project_shows_its_latest_plant_version(
    client,
    make_user,
    make_project,
    session,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await PlantVersionRepository(session).save_version(
        project.id,
        example_plant(),
        "",
        owner.id,
    )

    response = await client.get(f"{PROJECTS}/{project.id}", headers=bearer(owner))

    assert response.json()["plant_version"] == 1


async def test_case_with_missing_values_is_incomplete(
    client, make_user, make_project, session, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await CaseVersionRepository(session).save_version(
        project.id, example_case(), "Case", owner.id
    )

    response = await client.get(f"{PROJECTS}/{project.id}", headers=bearer(owner))

    step = response.json()["progress"]["case"]
    assert step["state"] == "incomplete"
    assert step["label"].startswith("Version 1")


async def test_case_with_all_its_values_is_ready(
    client, make_user, make_project, session, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    version = await CaseVersionRepository(session).save_version(
        project.id, example_case(), "Case", owner.id
    )
    await blobs.put("key", DEMAND_CSV)
    await CaseFileRepository(session).add(
        project.id, version.id, DEMAND_FILE, len(DEMAND_CSV), "key"
    )

    response = await client.get(f"{PROJECTS}/{project.id}", headers=bearer(owner))

    assert response.json()["progress"]["case"] == {
        "state": "ready",
        "label": "Version 1",
    }
