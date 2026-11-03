from tests.conftest import bearer

PROJECTS = "/api/v1/workspace/projects"


async def test_create_returns_the_contract_project(client, make_user) -> None:
    user = await make_user()

    response = await client.post(
        PROJECTS,
        json={"name": "  Doublet  "},
        headers=bearer(user),
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "id",
        "name",
        "owner",
        "plant_version",
        "case_version",
        "created",
        "updated",
        "progress",
        "chats",
        "runs",
        "budget",
        "memory",
        "mcp",
    }
    assert body["name"] == "Doublet"
    assert body["owner"] == {"id": str(user.id), "name": user.name}
    assert body["plant_version"] is None
    assert (body["chats"], body["runs"]) == (0, 0)
    assert body["budget"] == {"max_tokens": None, "max_cost": None}
    assert (body["memory"], body["mcp"]) == (None, [])
    assert body["created"].endswith("Z")


async def test_empty_name_is_refused(client, make_user) -> None:
    user = await make_user()

    response = await client.post(
        PROJECTS,
        json={"name": "   "},
        headers=bearer(user),
    )

    assert response.status_code == 422
    assert set(response.json()["error"]["details"]["fields"]) == {"name"}
