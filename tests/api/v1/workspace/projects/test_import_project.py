from uuid import UUID

import pytest

from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.gemini.plant import dump_plant, example_plant, load_plant
from src.core.settings import settings
from tests.api.v1.workspace.projects.archives import (
    PROJECT_FILE,
    archive_of,
    version_file,
)
from tests.conftest import bearer

PROJECTS = "/api/v1/workspace/projects"
IMPORT = f"{PROJECTS}/import"


def upload(data: bytes) -> dict:
    return {"file": ("project.zip", data, "application/zip")}


def changed_plant(stages: int) -> dict:
    plant = load_plant(example_plant())
    plant.update_params(**{"esp.no_stages": stages})
    return dump_plant(plant)


async def project_count(client, headers: dict) -> int:
    return len((await client.get(PROJECTS, headers=headers)).json()["items"])


async def test_export_then_import_gives_the_same_project(
    client,
    make_user,
    make_project,
    session,
) -> None:
    owner = await make_user()
    importer = await make_user("importer@example.com")
    project = await make_project(owner, "Field A")
    repository = PlantVersionRepository(session)
    await repository.save_version(project.id, changed_plant(1), "One", owner.id)
    await repository.save_version(project.id, changed_plant(2), "Two", owner.id)
    originals = await repository.all_versions(project.id)
    exported = await client.get(
        f"{PROJECTS}/{project.id}/export",
        headers=bearer(owner),
    )

    response = await client.post(
        IMPORT,
        files=upload(exported.content),
        headers=bearer(importer),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Field A"
    assert body["owner"]["id"] == str(importer.id)
    assert body["plant_version"] == 2
    imported = await repository.all_versions(UUID(body["id"]))
    assert [
        (version.number, version.note, version.created, version.digest)
        for version in imported
    ] == [
        (version.number, version.note, version.created, version.digest)
        for version in originals
    ]
    assert [version.content for version in imported] == [
        version.content for version in originals
    ]


async def test_import_reads_only_the_expected_files(client, make_user) -> None:
    user = await make_user()
    data = archive_of(
        {
            "project.json": PROJECT_FILE,
            "plant/1.json": version_file(),
            "plant/notes.json": "not json",
            "readme.txt": "ignored",
        }
    )

    response = await client.post(IMPORT, files=upload(data), headers=bearer(user))

    assert response.status_code == 201
    assert response.json()["plant_version"] == 1


@pytest.mark.parametrize(
    "path",
    ["../evil.json", "plant/../../evil.json", "/etc/evil.json", "..\\evil.json"],
)
async def test_unsafe_path_is_refused(client, make_user, path: str) -> None:
    user = await make_user()
    data = archive_of({"project.json": PROJECT_FILE, path: "{}"})
    headers = bearer(user)

    response = await client.post(IMPORT, files=upload(data), headers=headers)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert set(error["details"]["fields"]) == {"file"}
    assert await project_count(client, headers) == 0


async def test_bad_version_refuses_the_import_and_writes_nothing(
    client,
    make_user,
) -> None:
    user = await make_user()
    data = archive_of(
        {
            "project.json": PROJECT_FILE,
            "plant/1.json": version_file(1),
            "plant/2.json": version_file(2, {**example_plant(), "version": 9}),
        }
    )
    headers = bearer(user)

    response = await client.post(IMPORT, files=upload(data), headers=headers)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "plant_invalid"
    assert error["details"]["file"] == "plant/2.json"
    assert await project_count(client, headers) == 0


@pytest.mark.parametrize(
    "bad_file",
    ["not json", version_file(number=2), '{"number": 1}'],
    ids=["not-json", "wrong-number", "missing-fields"],
)
async def test_unreadable_version_is_plant_invalid(
    client,
    make_user,
    bad_file: str,
) -> None:
    user = await make_user()
    data = archive_of({"project.json": PROJECT_FILE, "plant/1.json": bad_file})

    response = await client.post(IMPORT, files=upload(data), headers=bearer(user))

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "plant_invalid"
    assert error["details"]["file"] == "plant/1.json"


async def test_unpacked_size_limit_is_refused(
    client,
    make_user,
    monkeypatch,
) -> None:
    user = await make_user()
    bomb = archive_of({"project.json": PROJECT_FILE, "big.bin": "0" * 100_000})
    monkeypatch.setattr(settings, "PROJECT_IMPORT_MAX_BYTES", 50_000)

    response = await client.post(IMPORT, files=upload(bomb), headers=bearer(user))

    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"] == {
        "file": "Archive is too large"
    }


async def test_upload_size_limit_is_refused(client, make_user, monkeypatch) -> None:
    user = await make_user()
    monkeypatch.setattr(settings, "PROJECT_IMPORT_MAX_BYTES", 10)

    response = await client.post(
        IMPORT,
        files=upload(archive_of({"project.json": PROJECT_FILE})),
        headers=bearer(user),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "data",
    [
        b"not a zip",
        archive_of({"readme.txt": "no project file"}),
        archive_of({"project.json": "not json"}),
        archive_of({"project.json": '{"format": 2, "name": "x"}'}),
    ],
    ids=["not-a-zip", "no-project-file", "bad-json", "wrong-format"],
)
async def test_bad_archive_is_refused(client, make_user, data: bytes) -> None:
    user = await make_user()

    response = await client.post(IMPORT, files=upload(data), headers=bearer(user))

    assert response.status_code == 422
    assert set(response.json()["error"]["details"]["fields"]) == {"file"}


async def test_missing_file_is_a_field_error(client, make_user) -> None:
    user = await make_user()

    response = await client.post(
        IMPORT,
        data={"other": "value"},
        headers=bearer(user),
    )

    assert response.status_code == 422
    assert set(response.json()["error"]["details"]["fields"]) == {"file"}
