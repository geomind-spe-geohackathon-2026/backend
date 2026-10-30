from src.core.security.jwt import create_token_pair

LOGOUT = "/api/v1/identity/authn/logout"


async def test_logout_revokes_access_and_refresh_tokens(client, make_user) -> None:
    user = await make_user()
    tokens = create_token_pair(user.id)
    headers = {"Authorization": f"Bearer {tokens.access_token}"}

    response = await client.post(LOGOUT, headers=headers)

    assert response.status_code == 204
    me = await client.get("/api/v1/identity/me", headers=headers)
    assert me.status_code == 401
    refresh = await client.post(
        "/api/v1/identity/authn/refresh",
        json={"refresh_token": tokens.refresh_token},
    )
    assert refresh.status_code == 401
