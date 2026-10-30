from tests.conftest import PASSWORD, bearer

CHANGE = "/api/v1/identity/me/password"
LOGIN = "/api/v1/identity/authn/login"


async def test_change_password_replaces_the_password(client, make_user) -> None:
    user = await make_user()

    response = await client.post(
        CHANGE,
        json={"old_password": PASSWORD, "new_password": "another-password"},
        headers=bearer(user),
    )

    assert response.status_code == 204
    login = await client.post(
        LOGIN,
        json={"email": user.email, "password": "another-password"},
    )
    assert login.status_code == 200


async def test_wrong_old_password_is_a_field_error(client, make_user) -> None:
    user = await make_user()

    response = await client.post(
        CHANGE,
        json={"old_password": "wrong-password", "new_password": "another-password"},
        headers=bearer(user),
    )

    assert response.status_code == 422
    assert set(response.json()["error"]["details"]["fields"]) == {"old_password"}
