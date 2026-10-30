from tests.conftest import bearer

USERS = "/api/v1/identity/users"


async def test_list_pages_through_every_user(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")
    await make_user("one@example.com")
    await make_user("two@example.com")
    headers = bearer(admin)

    first = (await client.get(USERS, params={"limit": 2}, headers=headers)).json()
    second = (
        await client.get(
            USERS,
            params={"limit": 2, "cursor": first["next"]},
            headers=headers,
        )
    ).json()

    assert second["next"] is None
    emails = [user["email"] for user in first["items"] + second["items"]]
    assert sorted(emails) == [
        "admin@example.com",
        "one@example.com",
        "two@example.com",
    ]


async def test_limit_above_maximum_is_refused(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")

    response = await client.get(
        USERS,
        params={"limit": 201},
        headers=bearer(admin),
    )

    assert response.status_code == 422
    assert set(response.json()["error"]["details"]["fields"]) == {"limit"}
