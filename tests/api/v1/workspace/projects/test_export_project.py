import json
from io import BytesIO
from zipfile import ZipFile

from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from tests.conftest import bearer
from tests.plants import example_plant

PROJECTS = "/api/v1/workspace/projects"


async def test_export_has_the_contract_layout(
    client,
    make_user,
    make_project,
    session,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    content = example_plant()
    await PlantVersionRepository(session).save_version(
        project.id,
        content,
        "First",
        owner.id,
    )

    response = await client.get(
        f"{PROJECTS}/{project.id}/export",
        headers=bearer(owner),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["plant/1.json", "project.json"]
        project_file = json.loads(archive.read("project.json"))
        version_file = json.loads(archive.read("plant/1.json"))
    assert set(project_file) == {"format", "name", "exported"}
    assert project_file["format"] == 1
    assert set(version_file) == {"number", "note", "created", "content"}
    assert version_file["content"] == content


async def test_other_member_cannot_export(client, make_user, make_project) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    project = await make_project(owner)

    response = await client.get(
        f"{PROJECTS}/{project.id}/export",
        headers=bearer(other),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"
