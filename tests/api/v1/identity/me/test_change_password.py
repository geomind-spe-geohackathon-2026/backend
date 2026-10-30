from src.core.security.jwt import create_token_pair
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


async def test_change_revokes_tokens_issued_before_it(client, make_user) -> None:
    user = await make_user()
    tokens = create_token_pair(user.id)
    headers = {"Authorization": f"Bearer {tokens.access_token}"}

    await client.post(
        CHANGE,
        json={"old_password": PASSWORD, "new_password": "another-password"},
        headers=headers,
    )

    me = await client.get("/api/v1/identity/me", headers=headers)
    assert me.status_code == 401
    refresh = await client.post(
        "/api/v1/identity/authn/refresh",
        json={"refresh_token": tokens.refresh_token},
    )
    assert refresh.status_code == 401


async def test_tokens_from_the_new_password_work(client, make_user) -> None:
    user = await make_user()
    await client.post(
        CHANGE,
        json={"old_password": PASSWORD, "new_password": "another-password"},
        headers=bearer(user),
    )

    login = await client.post(
        LOGIN,
        json={"email": user.email, "password": "another-password"},
    )

    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await client.get("/api/v1/identity/me", headers=headers)
    assert me.status_code == 200
