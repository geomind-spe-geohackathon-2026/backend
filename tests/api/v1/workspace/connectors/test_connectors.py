import geomind as gd

from src.core.clients.postgres.repositories.connector import ConnectorRepository
from tests.conftest import bearer
from tests.geomind_doubles import mcp_with

URL = "/api/v1/workspace/connectors"
TOOLS = [{"name": "search", "description": "Find a well", "read_only": True}]


async def admin_of(make_user):
    return await make_user("admin@example.com", role="admin")


async def test_a_connector_is_added_checked_and_its_secret_never_shown(
    client, session, make_user, monkeypatch
) -> None:
    seen = []
    monkeypatch.setattr(gd, "mcp", mcp_with(TOOLS, seen=seen), raising=False)
    admin = await admin_of(make_user)

    response = await client.post(
        URL,
        json={
            "name": "wells",
            "url": "https://mcp.example.com/mcp",
            "auth": "bearer",
            "secret": "s3cret",
        },
        headers=bearer(admin),
    )

    body = response.json()
    assert response.status_code == 201, response.text
    assert body["status"] == "ok" and body["tools"] == TOOLS
    assert body["has_secret"] is True
    assert "s3cret" not in response.text
    assert seen[0]["headers"] == {"Authorization": "Bearer s3cret"}
    stored = await ConnectorRepository(session).get_by_name("wells")
    assert stored.secret != "s3cret"


async def test_a_refused_sign_in_is_kept_as_an_error(
    client, make_user, monkeypatch
) -> None:
    monkeypatch.setattr(gd, "mcp", mcp_with(error="auth_refused"), raising=False)
    admin = await admin_of(make_user)

    response = await client.post(
        URL,
        json={"name": "wells", "url": "https://mcp.example.com/mcp"},
        headers=bearer(admin),
    )

    assert response.json()["status"] == "error"
    assert response.json()["error"].startswith("auth_refused")


async def test_without_geomind_mcp_a_connector_stays_unchecked(
    client, make_user, monkeypatch
) -> None:
    monkeypatch.delattr(gd, "mcp", raising=False)
    admin = await admin_of(make_user)

    response = await client.post(
        URL,
        json={"name": "wells", "url": "https://mcp.example.com/mcp"},
        headers=bearer(admin),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "unchecked"


async def test_names_must_fit_a_tool_name(client, make_user) -> None:
    admin = await admin_of(make_user)
    response = await client.post(
        URL,
        json={"name": "Wells DB", "url": "https://x.example.com"},
        headers=bearer(admin),
    )
    assert response.status_code == 422


async def test_a_header_sign_in_needs_its_header_and_secret(client, make_user) -> None:
    admin = await admin_of(make_user)
    response = await client.post(
        URL,
        json={"name": "wells", "url": "https://x.example.com", "auth": "header"},
        headers=bearer(admin),
    )
    assert response.status_code == 422


async def test_changing_the_address_clears_the_check_and_members_only_read(
    client, make_user, monkeypatch
) -> None:
    monkeypatch.setattr(gd, "mcp", mcp_with(TOOLS), raising=False)
    admin = await admin_of(make_user)
    member = await make_user()
    created = await client.post(
        URL,
        json={"name": "wells", "url": "https://a.example.com"},
        headers=bearer(admin),
    )
    connector = created.json()["id"]

    changed = await client.patch(
        f"{URL}/{connector}",
        json={"url": "https://b.example.com"},
        headers=bearer(admin),
    )
    refused = await client.delete(f"{URL}/{connector}", headers=bearer(member))
    listed = await client.get(URL, headers=bearer(member))
    deleted = await client.delete(f"{URL}/{connector}", headers=bearer(admin))

    assert changed.json()["status"] == "unchecked" and changed.json()["tools"] == []
    assert refused.status_code == 403
    assert [item["name"] for item in listed.json()] == ["wells"]
    assert deleted.status_code == 204


async def test_a_project_chooses_memory_and_connectors(
    client, make_user, make_project, monkeypatch
) -> None:
    monkeypatch.setattr(gd, "mcp", mcp_with(TOOLS), raising=False)
    admin = await admin_of(make_user)
    project = await make_project(admin)
    created = await client.post(
        URL,
        json={"name": "wells", "url": "https://a.example.com"},
        headers=bearer(admin),
    )
    connector = created.json()["id"]
    path = f"/api/v1/workspace/projects/{project.id}"

    chosen = await client.patch(
        path, json={"memory": "off", "connectors": [connector]}, headers=bearer(admin)
    )
    unknown = await client.patch(
        path,
        json={"connectors": ["00000000-0000-0000-0000-000000000000"]},
        headers=bearer(admin),
    )

    assert chosen.json()["memory"] == "off"
    assert chosen.json()["connectors"] == [connector]
    assert unknown.status_code == 422
