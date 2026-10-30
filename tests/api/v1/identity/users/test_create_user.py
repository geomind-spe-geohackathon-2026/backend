from tests.conftest import bearer

USERS = "/api/v1/identity/users"
NEW_USER = {
    "email": "New@Example.com",
    "name": "New User",
    "password": "correct-password",
    "role": "member",
}


async def test_create_user_returns_the_contract_user(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")

    response = await client.post(USERS, json=NEW_USER, headers=bearer(admin))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "name", "role", "active"}
    assert body["email"] == "new@example.com"
    assert body["active"] is True


async def test_duplicate_email_is_a_conflict(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")
    headers = bearer(admin)

    await client.post(USERS, json=NEW_USER, headers=headers)
    response = await client.post(USERS, json=NEW_USER, headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_unknown_role_is_refused(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")

    response = await client.post(
        USERS,
        json={**NEW_USER, "role": "owner"},
        headers=bearer(admin),
    )

    assert response.status_code == 422
    assert set(response.json()["error"]["details"]["fields"]) == {"role"}


async def test_member_cannot_create_users(client, make_user) -> None:
    member = await make_user()

    response = await client.post(USERS, json=NEW_USER, headers=bearer(member))

    assert response.status_code == 403
