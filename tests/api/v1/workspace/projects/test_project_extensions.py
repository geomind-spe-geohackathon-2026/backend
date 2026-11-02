import json
from io import BytesIO
from uuid import UUID
from zipfile import ZipFile

from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from tests.api.v1.workspace.projects.archives import PROJECT_FILE, archive_of
from tests.cases import DEMAND_CSV, DEMAND_FILE, broken_case, example_case
from tests.conftest import bearer

PROJECTS = "/api/v1/workspace/projects"


def case_file(content: dict) -> str:
    return json.dumps(
        {
            "number": 1,
            "note": "Demand",
            "created": "2026-10-30T12:00:00+00:00",
            "content": content,
        }
    )


CASE_FILE = case_file(example_case())


async def test_search_filters_by_name(client, make_user, make_project) -> None:
    user = await make_user()
    await make_project(user, "Delft heating")
    await make_project(user, "Rotterdam district")

    response = await client.get(
        PROJECTS, params={"search": "DELFT"}, headers=bearer(user)
    )

    assert [item["name"] for item in response.json()["items"]] == ["Delft heating"]


async def test_search_treats_wildcards_as_text(client, make_user, make_project) -> None:
    user = await make_user()
    await make_project(user, "Delft")

    response = await client.get(PROJECTS, params={"search": "%"}, headers=bearer(user))

    assert response.json()["items"] == []


async def test_patch_renames_the_project(client, make_user, make_project) -> None:
    user = await make_user()
    project = await make_project(user)

    response = await client.patch(
        f"{PROJECTS}/{project.id}",
        json={"name": " Renamed "},
        headers=bearer(user),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


async def test_patch_refuses_an_empty_name_and_a_stranger(
    client,
    make_user,
    make_project,
) -> None:
    owner = await make_user()
    stranger = await make_user("other@example.com")
    project = await make_project(owner)

    empty = await client.patch(
        f"{PROJECTS}/{project.id}", json={"name": " "}, headers=bearer(owner)
    )
    other = await client.patch(
        f"{PROJECTS}/{project.id}", json={"name": "x"}, headers=bearer(stranger)
    )

    assert empty.status_code == 422
    assert other.status_code == 404


async def test_project_shows_case_version_and_progress(
    client,
    make_user,
    make_project,
    session,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await CaseVersionRepository(session).save_version(
        project.id, {"a": 1}, "", owner.id
    )

    body = (await client.get(f"{PROJECTS}/{project.id}", headers=bearer(owner))).json()

    assert body["case_version"] == 1
    assert body["progress"]["case"] == {"state": "ready", "label": "Version 1"}
    assert body["progress"]["plant"]["state"] == "empty"


async def test_list_carries_progress(client, make_user, make_project, session) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await make_project(owner)
    await CaseVersionRepository(session).save_version(
        project.id, {"a": 1}, "", owner.id
    )

    items = (await client.get(PROJECTS, headers=bearer(owner))).json()["items"]

    by_id = {item["id"]: item for item in items}
    assert by_id[str(project.id)]["case_version"] == 1
    assert sum(item["case_version"] is None for item in items) == 1


async def test_export_has_case_versions_and_files(
    client,
    make_user,
    make_project,
    session,
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    version = await CaseVersionRepository(session).save_version(
        project.id, example_case(), "Demand", owner.id
    )
    await blobs.put("key-1", DEMAND_CSV)
    await CaseFileRepository(session).add(
        project.id, version.id, DEMAND_FILE, 15, "key-1"
    )

    response = await client.get(
        f"{PROJECTS}/{project.id}/export", headers=bearer(owner)
    )

    with ZipFile(BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == [
            "case/1.json",
            f"case/files/1/{DEMAND_FILE}",
            "project.json",
        ]
        assert archive.read(f"case/files/1/{DEMAND_FILE}") == DEMAND_CSV
        assert json.loads(archive.read("case/1.json"))["content"] == version.content


async def test_import_restores_case_versions_and_files(
    client,
    make_user,
    session,
    blobs,
) -> None:
    user = await make_user()
    archive = archive_of(
        {
            "project.json": PROJECT_FILE,
            "case/1.json": CASE_FILE,
            f"case/files/1/{DEMAND_FILE}": DEMAND_CSV.decode(),
        }
    )

    response = await client.post(
        f"{PROJECTS}/import",
        files={"file": ("project.zip", archive, "application/zip")},
        headers=bearer(user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["case_version"] == 1
    stored = await CaseVersionRepository(session).latest_version(UUID(body["id"]))
    files = await CaseFileRepository(session).list_for_version(stored.id)
    assert [file.name for file in files] == [DEMAND_FILE]
    assert blobs.objects[files[0].object_key] == DEMAND_CSV


async def test_import_refuses_a_file_without_its_case_version(
    client,
    make_user,
    blobs,
) -> None:
    user = await make_user()
    archive = archive_of({"project.json": PROJECT_FILE, "case/files/2/demand.csv": "x"})

    response = await client.post(
        f"{PROJECTS}/import",
        files={"file": ("project.zip", archive, "application/zip")},
        headers=bearer(user),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert blobs.objects == {}


async def test_import_refuses_a_case_version_that_is_not_a_document(
    client,
    make_user,
) -> None:
    user = await make_user()
    broken = json.dumps(
        {"number": 1, "note": "", "created": "2026-10-30T12:00:00+00:00", "content": []}
    )

    response = await client.post(
        f"{PROJECTS}/import",
        files={
            "file": (
                "p.zip",
                archive_of({"project.json": PROJECT_FILE, "case/1.json": broken}),
                "application/zip",
            )
        },
        headers=bearer(user),
    )

    assert response.status_code == 422


async def test_import_refuses_a_case_gemini_calls_invalid(client, make_user) -> None:
    user = await make_user()
    archive = archive_of(
        {
            "project.json": PROJECT_FILE,
            "case/1.json": case_file(broken_case()),
            f"case/files/1/{DEMAND_FILE}": DEMAND_CSV.decode(),
        }
    )

    response = await client.post(
        f"{PROJECTS}/import",
        files={"file": ("project.zip", archive, "application/zip")},
        headers=bearer(user),
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "case_invalid"
    assert error["details"]["problems"][0]["file"] == "case/1.json"
