from uuid import uuid4

import pytest

from tests.conftest import bearer

USERS = "/api/v1/identity/users"


async def test_update_changes_only_the_given_fields(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")
    member = await make_user()

    response = await client.patch(
        f"{USERS}/{member.id}",
        json={"name": "Renamed", "role": "admin"},
        headers=bearer(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["role"], body["active"]) == ("Renamed", "admin", True)


async def test_deactivated_user_loses_access(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")
    member = await make_user()
    member_headers = bearer(member)

    response = await client.patch(
        f"{USERS}/{member.id}",
        json={"active": False},
        headers=bearer(admin),
    )

    assert response.json()["active"] is False
    me = await client.get("/api/v1/identity/me", headers=member_headers)
    assert me.status_code == 401


@pytest.mark.parametrize("change", [{"active": False}, {"role": "member"}])
async def test_admin_cannot_remove_own_access(client, make_user, change) -> None:
    admin = await make_user("admin@example.com", role="admin")

    response = await client.patch(
        f"{USERS}/{admin.id}",
        json=change,
        headers=bearer(admin),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_admin_can_rename_themselves(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")

    response = await client.patch(
        f"{USERS}/{admin.id}",
        json={"name": "Root", "role": "admin", "active": True},
        headers=bearer(admin),
    )

    assert response.status_code == 200


async def test_unknown_user_is_not_found(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")

    response = await client.patch(
        f"{USERS}/{uuid4()}",
        json={"name": "Nobody"},
        headers=bearer(admin),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"
