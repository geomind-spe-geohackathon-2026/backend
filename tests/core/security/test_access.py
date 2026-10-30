from tests.conftest import bearer

USERS = "/api/v1/identity/users"


async def test_admin_passes_admin_route(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")

    response = await client.get(USERS, headers=bearer(admin))

    assert response.status_code == 200


async def test_member_is_forbidden_on_admin_route(client, make_user) -> None:
    member = await make_user()

    response = await client.get(USERS, headers=bearer(member))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_token_of_inactive_user_is_refused(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin", active=False)

    response = await client.get(USERS, headers=bearer(admin))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
