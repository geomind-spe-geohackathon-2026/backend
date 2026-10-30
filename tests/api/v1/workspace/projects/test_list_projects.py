from tests.conftest import bearer

PROJECTS = "/api/v1/workspace/projects"


async def test_member_lists_only_their_projects(
    client,
    make_user,
    make_project,
) -> None:
    member = await make_user()
    other = await make_user("other@example.com")
    own = await make_project(member)
    await make_project(other)

    response = await client.get(PROJECTS, headers=bearer(member))

    assert [item["id"] for item in response.json()["items"]] == [str(own.id)]


async def test_admin_lists_all_projects(client, make_user, make_project) -> None:
    admin = await make_user("admin@example.com", role="admin")
    member = await make_user()
    await make_project(member)
    await make_project(admin)

    response = await client.get(PROJECTS, headers=bearer(admin))

    assert len(response.json()["items"]) == 2


async def test_list_pages_with_a_cursor(client, make_user, make_project) -> None:
    member = await make_user()
    for _ in range(3):
        await make_project(member)
    headers = bearer(member)

    first = (await client.get(PROJECTS, params={"limit": 2}, headers=headers)).json()
    second = (
        await client.get(
            PROJECTS,
            params={"limit": 2, "cursor": first["next"]},
            headers=headers,
        )
    ).json()

    assert len(first["items"]) == 2
    assert len(second["items"]) == 1
    assert second["next"] is None
