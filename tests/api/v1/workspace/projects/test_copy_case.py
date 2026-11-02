from sqlalchemy import select

from src.core.clients.postgres.models.project import Project
from tests.api.v1.design.case.test_case import save_case, upload
from tests.cases import DEMAND_CSV, DEMAND_FILE, example_case
from tests.conftest import bearer

PROJECTS = "/api/v1/workspace/projects"


async def seed(client, owner, make_project, blobs):
    source = await make_project(owner, "Source")
    await save_case(client, bearer(owner), source)
    await save_case(
        client, bearer(owner), source, base=1, content={**example_case(), "name": "v2"}
    )
    await upload(client, bearer(owner), source, 2)
    return source


async def test_case_from_copies_the_content_and_files_as_version_one(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    source = await seed(client, owner, make_project, blobs)

    response = await client.post(
        PROJECTS,
        json={"name": "Copy", "case_from": str(source.id)},
        headers=bearer(owner),
    )

    assert response.status_code == 201
    created = response.json()
    assert created["case_version"] == 1
    fetched = await client.get(
        "/api/v1/design/case",
        params={"project": created["id"]},
        headers=bearer(owner),
    )
    assert fetched.json()["content"]["name"] == "v2"
    copied = [
        data
        for key, data in blobs.objects.items()
        if key.startswith(f"projects/{created['id']}/")
    ]
    assert copied == [DEMAND_CSV]
    assert DEMAND_FILE in str(fetched.json()["files"])


async def test_case_from_a_project_without_a_case_creates_nothing(
    client, make_user, make_project, blobs, session
) -> None:
    owner = await make_user()
    source = await make_project(owner, "Empty")

    response = await client.post(
        PROJECTS,
        json={"name": "Copy", "case_from": str(source.id)},
        headers=bearer(owner),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "case_not_found"
    names = list(await session.scalars(select(Project.name)))
    assert names == ["Empty"]


async def test_case_from_an_unknown_project_is_not_found(
    client, make_user, blobs
) -> None:
    owner = await make_user()

    response = await client.post(
        PROJECTS,
        json={"name": "Copy", "case_from": "00000000-0000-4000-8000-000000000000"},
        headers=bearer(owner),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


async def test_case_from_a_project_the_user_cannot_see_is_not_found(
    client, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    source = await seed(client, owner, make_project, blobs)

    response = await client.post(
        PROJECTS,
        json={"name": "Copy", "case_from": str(source.id)},
        headers=bearer(other),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"
