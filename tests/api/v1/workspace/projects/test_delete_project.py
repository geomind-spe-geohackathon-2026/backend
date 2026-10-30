from tests.conftest import bearer

PROJECTS = "/api/v1/workspace/projects"


async def test_owner_deletes_project(client, make_user, make_project) -> None:
    owner = await make_user()
    project = await make_project(owner)
    headers = bearer(owner)

    response = await client.delete(f"{PROJECTS}/{project.id}", headers=headers)

    assert response.status_code == 204
    gone = await client.get(f"{PROJECTS}/{project.id}", headers=headers)
    assert gone.status_code == 404


async def test_other_member_cannot_delete(client, make_user, make_project) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    project = await make_project(owner)

    response = await client.delete(
        f"{PROJECTS}/{project.id}",
        headers=bearer(other),
    )

    assert response.status_code == 404
    still_there = await client.get(f"{PROJECTS}/{project.id}", headers=bearer(owner))
    assert still_there.status_code == 200
