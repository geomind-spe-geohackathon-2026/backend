from tests.conftest import PASSWORD

LOGIN = "/api/v1/identity/authn/login"


async def test_login_returns_tokens_and_user(client, make_user) -> None:
    user = await make_user()

    response = await client.post(
        LOGIN,
        json={"email": user.email, "password": PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "refresh_token", "user"}
    assert body["user"] == {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": "member",
        "active": True,
    }


async def test_wrong_password_is_unauthorized(client, make_user) -> None:
    user = await make_user()

    response = await client.post(
        LOGIN,
        json={"email": user.email, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_inactive_user_cannot_sign_in(client, make_user) -> None:
    user = await make_user(active=False)

    response = await client.post(
        LOGIN,
        json={"email": user.email, "password": PASSWORD},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_unknown_domain_or_short_password_is_unauthorized_not_a_field_error(
    client,
) -> None:
    reserved = await client.post(
        LOGIN, json={"email": "admin@example.test", "password": PASSWORD}
    )
    short = await client.post(LOGIN, json={"email": "a@example.com", "password": "x"})

    assert reserved.status_code == 401
    assert short.status_code == 401
    assert reserved.json()["error"]["message"] == short.json()["error"]["message"]
