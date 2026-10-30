from uuid import uuid4

from tests.conftest import bearer

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
