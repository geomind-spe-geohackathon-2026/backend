from src.core.clients.postgres.repositories.user import UserRepository
from src.core.security.jwt import create_token_pair

REFRESH = "/api/v1/identity/authn/refresh"


async def test_refresh_returns_a_new_pair(client, make_user) -> None:
    user = await make_user()
    tokens = create_token_pair(user.id)

    response = await client.post(REFRESH, json={"refresh_token": tokens.refresh_token})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "refresh_token"}
    me = await client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.json()["id"] == str(user.id)


async def test_refresh_token_works_once(client, make_user) -> None:
    user = await make_user()
    tokens = create_token_pair(user.id)
    payload = {"refresh_token": tokens.refresh_token}

    await client.post(REFRESH, json=payload)
    response = await client.post(REFRESH, json=payload)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_access_token_cannot_refresh(client, make_user) -> None:
    user = await make_user()
    tokens = create_token_pair(user.id)

    response = await client.post(REFRESH, json={"refresh_token": tokens.access_token})

    assert response.status_code == 401


async def test_inactive_user_cannot_refresh(
    client,
    make_user,
    session_factory,
) -> None:
    user = await make_user()
    tokens = create_token_pair(user.id)
    async with session_factory() as session:
        repository = UserRepository(session)
        await repository.update(await repository.get_by_id(user.id), {"active": False})

    response = await client.post(REFRESH, json={"refresh_token": tokens.refresh_token})

    assert response.status_code == 401
