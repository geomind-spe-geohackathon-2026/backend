import geomind as gd
import pytest

from src.core.clients.postgres.repositories.mcp_server import McpServerRepository
from src.core.geomind import mcp as core_mcp
from tests.conftest import bearer
from tests.geomind_doubles import FakeMcpServer

URL = "/api/v1/workspace/mcp"
TOOLS = [
    {"name": "search", "description": "Find a well", "read_only": True},
    {"name": "write", "description": "Write a note", "read_only": False},
]


@pytest.fixture
def serve(monkeypatch):
    """Answer geomind's real MCP client from a fake server; no network is reached."""
    monkeypatch.setenv("GEOMIND_MCP_TIMEOUT", "5")

    def start(**options) -> FakeMcpServer:
        server = FakeMcpServer(**options)
        monkeypatch.setattr(core_mcp, "TRANSPORT", server.transport())
        return server

    return start


def statuses(body: dict) -> dict[str, str]:
    return {step["name"]: step["status"] for step in body["steps"]}


async def admin_of(make_user):
    return await make_user("admin@example.com", role="admin")


async def test_a_connector_is_added_checked_and_its_secret_never_shown(
    client, session, make_user, serve
) -> None:
    server = serve(token="s3cret")
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
    assert body["error"] is None
    steps = ("reachable", "initialize", "auth", "tools")
    assert statuses(body) == dict.fromkeys(steps, "ok")
    assert body["server_info"] == {"name": None, "version": None, "protocol": None}
    assert isinstance(body["elapsed_ms"], int)
    assert body["has_secret"] is True
    assert "s3cret" not in response.text
    assert server.seen[0]["authorization"] == "Bearer s3cret"
    stored = await McpServerRepository(session).get_by_name("wells")
    assert stored.secret != "s3cret"


async def test_a_refused_sign_in_is_kept_as_an_error(client, make_user, serve) -> None:
    serve(token="right")
    admin = await admin_of(make_user)

    response = await client.post(
        URL,
        json={
            "name": "wells",
            "url": "https://mcp.example.com/mcp",
            "auth": "bearer",
            "secret": "wrong-secret",
        },
        headers=bearer(admin),
    )

    body = response.json()
    assert body["status"] == "error"
    assert body["error"] == "auth_refused: The server refused the credentials"
    assert statuses(body) == {
        "reachable": "ok",
        "initialize": "failed",
        "auth": "failed",
        "tools": "skipped",
    }
    assert "wrong-secret" not in response.text


async def test_an_unreachable_server_fails_the_first_step(
    client, make_user, serve
) -> None:
    serve(down=True)
    admin = await admin_of(make_user)

    response = await client.post(
        URL,
        json={"name": "wells", "url": "https://mcp.example.com/mcp"},
        headers=bearer(admin),
    )

    body = response.json()
    assert body["status"] == "error" and body["tools"] == []
    assert body["error"].startswith("unreachable: ")
    assert "ConnectError" not in response.text
    assert statuses(body)["reachable"] == "failed"
    assert statuses(body)["tools"] == "skipped"


async def test_a_failed_listing_names_its_step_and_status(
    client, make_user, serve
) -> None:
    server = serve(fail="tools/list", status=503)
    admin = await admin_of(make_user)
    created = await client.post(
        URL,
        json={"name": "wells", "url": "https://mcp.example.com/mcp"},
        headers=bearer(admin),
    )
    server.fail = None
    server.error = "tools are off today"

    checked = await client.post(
        f"{URL}/{created.json()['id']}/check", headers=bearer(admin)
    )

    first = created.json()
    assert first["error"] == "bad_response: The server answered HTTP 503"
    assert statuses(first) == {
        "reachable": "ok",
        "initialize": "ok",
        "auth": "ok",
        "tools": "failed",
    }
    second = checked.json()
    tools = next(step for step in second["steps"] if step["name"] == "tools")
    assert tools["reason"] == "The server answered with an error: tools are off today"


async def test_a_list_has_no_check_steps(client, make_user, serve) -> None:
    serve()
    admin = await admin_of(make_user)
    await client.post(
        URL,
        json={"name": "wells", "url": "https://mcp.example.com/mcp"},
        headers=bearer(admin),
    )

    listed = await client.get(URL, headers=bearer(admin))

    item = listed.json()[0]
    assert item["status"] == "ok" and item["steps"] is None


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
    client, make_user, serve
) -> None:
    serve()
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
    client, make_user, make_project, serve
) -> None:
    serve()
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
        path, json={"memory": "off", "mcp": [connector]}, headers=bearer(admin)
    )
    unknown = await client.patch(
        path,
        json={"mcp": ["00000000-0000-0000-0000-000000000000"]},
        headers=bearer(admin),
    )

    assert chosen.json()["memory"] == "off"
    assert chosen.json()["mcp"] == [connector]
    assert unknown.status_code == 422
