from src.core.settings import settings
from tests.cases import DEMAND_CSV, DEMAND_FILE, broken_case, example_case
from tests.conftest import bearer
from tests.routes import route_exists

CASE = "/api/v1/design/case"


async def save_case(client, headers, project, base=None, content=None):
    return await client.post(
        CASE,
        headers=headers,
        json={
            "project": str(project.id),
            "base": base,
            "note": "first",
            "content": content or example_case(),
        },
    )


async def upload(client, headers, project, base, data=DEMAND_CSV, name=DEMAND_FILE):
    return await client.post(
        f"{CASE}/files",
        headers=headers,
        data={"project": str(project.id), "base": str(base), "name": name},
        files={"file": ("upload.csv", data, "text/csv")},
    )


async def test_no_case_is_case_not_found(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.get(
        CASE, params={"project": str(project.id)}, headers=bearer(owner)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "case_not_found"


async def test_saved_case_lists_missing_values_and_keeps_content(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    saved = await save_case(client, bearer(owner), project)
    read = await client.get(
        CASE, params={"project": str(project.id)}, headers=bearer(owner)
    )

    assert saved.status_code == 201
    assert read.json() == saved.json()
    body = saved.json()
    assert body["content"] == example_case()
    assert body["version"] == 1
    assert body["problems"] == []
    assert [item["path"] for item in body["missing"]] == ["demand.heating.power.file"]


async def test_structural_problem_is_case_invalid(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await save_case(client, bearer(owner), project, content=broken_case())

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "case_invalid"
    assert error["details"]["problems"][0]["code"] == "invalid_unit"


async def test_stale_base_and_identical_content_are_conflicts(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)

    stale = await save_case(client, bearer(owner), project, base=None)
    same = await save_case(client, bearer(owner), project, base=1)

    assert stale.status_code == same.status_code == 409
    assert stale.json()["error"]["details"] == {"latest": 1}


async def test_validate_returns_missing_and_problems(client, make_user, blobs) -> None:
    user = await make_user()

    incomplete = await client.post(
        f"{CASE}/validate", headers=bearer(user), json={"content": example_case()}
    )
    broken = await client.post(
        f"{CASE}/validate", headers=bearer(user), json={"content": broken_case()}
    )

    assert len(incomplete.json()["missing"]) == 1
    assert incomplete.json()["problems"] == []
    assert broken.json()["problems"][0]["code"] == "invalid_unit"


async def test_validate_with_a_project_finds_its_saved_files(
    client, make_user, make_project, blobs
) -> None:
    user = await make_user()
    project = await make_project(user)
    headers = bearer(user)
    await save_case(client, headers, project)
    await upload(client, headers, project, 1)

    response = await client.post(
        f"{CASE}/validate",
        headers=headers,
        json={"content": example_case(), "project": str(project.id)},
    )

    assert response.json()["missing"] == []
    assert response.json()["problems"] == []


async def test_validate_refuses_the_project_of_another_user(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    project = await make_project(owner)

    response = await client.post(
        f"{CASE}/validate",
        headers=bearer(other),
        json={"content": example_case(), "project": str(project.id)},
    )

    assert response.status_code == 404


async def test_schema_is_geminis_case_schema(client, make_user) -> None:
    user = await make_user()

    response = await client.get(f"{CASE}/schema", headers=bearer(user))

    assert response.status_code == 200
    assert response.json()["title"] == "Case"


async def test_schema_fixes_the_kind_of_a_case_document(client, make_user) -> None:
    user = await make_user()

    response = await client.get(f"{CASE}/schema", headers=bearer(user))

    assert response.json()["properties"]["kind"]["const"] == "case"


async def test_uploading_the_file_completes_the_case(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)

    response = await upload(client, bearer(owner), project, 1)

    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 2
    assert body["missing"] == []
    assert body["files"] == [{"name": DEMAND_FILE, "size": len(DEMAND_CSV)}]


async def test_uploading_needs_a_case_and_a_safe_name(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    none = await upload(client, bearer(owner), project, 1)
    await save_case(client, bearer(owner), project)
    unsafe = await upload(client, bearer(owner), project, 1, name="../x.csv")

    assert none.json()["error"]["code"] == "case_not_found"
    assert unsafe.json()["error"]["code"] == "validation_failed"


async def test_same_file_twice_is_conflict(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)
    await upload(client, bearer(owner), project, 1)

    again = await upload(client, bearer(owner), project, 2)

    assert again.status_code == 409


async def test_a_bad_file_is_case_invalid(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)

    response = await upload(client, bearer(owner), project, 1, data=b"time,other\n")

    assert response.status_code == 422
    assert response.json()["error"]["code"] in {"case_invalid"}


async def test_next_case_version_keeps_the_files(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)
    await upload(client, bearer(owner), project, 1)
    content = example_case()
    content["name"] = "renamed"

    response = await save_case(client, bearer(owner), project, 2, content)

    assert response.status_code == 201
    assert response.json()["missing"] == []
    assert [item["name"] for item in response.json()["files"]] == [DEMAND_FILE]


async def test_file_is_read_by_name_and_version(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)
    await upload(client, bearer(owner), project, 1)
    query = {"project": str(project.id)}

    latest = await client.get(
        f"{CASE}/files/{DEMAND_FILE}", params=query, headers=bearer(owner)
    )
    first = await client.get(
        f"{CASE}/files/{DEMAND_FILE}",
        params={**query, "version": 1},
        headers=bearer(owner),
    )
    unknown = await client.get(
        f"{CASE}/files/nope.csv", params=query, headers=bearer(owner)
    )

    assert latest.content == DEMAND_CSV
    assert latest.headers["content-type"].startswith("text/csv")
    assert first.json()["error"]["code"] == "case_file_not_found"
    assert unknown.json()["error"]["code"] == "case_file_not_found"


async def test_series_are_read_through_gemini(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)
    await upload(client, bearer(owner), project, 1)

    response = await client.get(
        f"{CASE}/series", params={"project": str(project.id)}, headers=bearer(owner)
    )

    series = response.json()["series"]
    assert series[0]["name"] == "demand.heating.power"
    assert series[0]["unit"] == "MW"
    assert series[0]["points"][0] == ["2030-01-01T00:00:00+00:00", 1.5]


async def test_series_are_served_while_other_values_are_missing(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    headers = bearer(owner)
    content = example_case()
    content["site"] = {"ground": {"gradient": {"unit": "K/m"}}}
    await save_case(client, headers, project, content=content)
    await upload(client, headers, project, 1)

    response = await client.get(
        f"{CASE}/series", params={"project": str(project.id)}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["series"][0]["name"] == "demand.heating.power"


async def test_series_of_an_incomplete_case_is_missing_inputs(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)

    response = await client.get(
        f"{CASE}/series", params={"project": str(project.id)}, headers=bearer(owner)
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "missing_inputs"
    assert error["details"]["missing"][0]["path"] == "demand.heating.power.file"


async def test_versions_are_newest_first(
    client, make_user, make_project, blobs, session
) -> None:
    from src.core.clients.postgres.repositories.activity import ActivityRepository

    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)
    await upload(client, bearer(owner), project, 1)

    response = await client.get(
        f"{CASE}/versions", params={"project": str(project.id)}, headers=bearer(owner)
    )

    items = response.json()["items"]
    assert [item["number"] for item in items] == [2, 1]
    assert items[0]["author"]["name"] == owner.name
    rows = await ActivityRepository(session).latest(project.id, 5)
    assert {row.text for row in rows} == {
        "Saved case version 1",
        "Saved case version 2",
    }
    assert all(route_exists(row.link_route, row.link_id) for row in rows)
    assert {row.link_route for row in rows} == {"design/case"}


async def test_other_member_cannot_read_or_save(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    project = await make_project(owner)

    read = await client.get(
        CASE, params={"project": str(project.id)}, headers=bearer(other)
    )
    save = await save_case(client, bearer(other), project)

    assert (
        read.json()["error"]["code"]
        == save.json()["error"]["code"]
        == "project_not_found"
    )


async def test_empty_form_base_means_no_version_yet(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)

    response = await upload(client, bearer(owner), project, "")

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"latest": 1}


async def test_every_later_version_still_reads_the_earlier_file(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    headers = bearer(owner)
    project = await make_project(owner)
    await save_case(client, headers, project)
    await upload(client, headers, project, 1)
    renamed = example_case()
    renamed["name"] = "renamed"
    await save_case(client, headers, project, 2, renamed)
    await upload(client, headers, project, 3, data=DEMAND_CSV, name="other.csv")
    query = {"project": str(project.id)}

    for number in (2, 3, 4):
        response = await client.get(
            f"{CASE}/files/{DEMAND_FILE}",
            params={**query, "version": number},
            headers=headers,
        )
        assert response.content == DEMAND_CSV, number
    latest = await client.get(f"{CASE}", params=query, headers=headers)
    assert sorted(item["name"] for item in latest.json()["files"]) == sorted(
        [DEMAND_FILE, "other.csv"]
    )


async def test_a_file_above_the_upload_limit_is_refused(
    client, make_user, make_project, blobs, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "PROJECT_IMPORT_MAX_BYTES", len(DEMAND_CSV) - 1)
    owner = await make_user()
    project = await make_project(owner)
    await save_case(client, bearer(owner), project)

    response = await upload(client, bearer(owner), project, 1)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert blobs.objects == {}
