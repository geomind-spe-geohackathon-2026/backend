from tests.conftest import bearer


async def test_get_me_returns_the_contract_user(client, make_user) -> None:
    user = await make_user()

    response = await client.get("/api/v1/identity/me", headers=bearer(user))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": "member",
        "active": True,
    }
