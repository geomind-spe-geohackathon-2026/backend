import geomind as gd
import pytest

from src.core.geomind import mcp
from tests.geomind_doubles import FakeMcpServer

SERVER = {
    "name": "wells",
    "url": "https://mcp.example.com/mcp",
    "transport": "http",
    "headers": {"Authorization": "Bearer s3cret"},
}


@pytest.fixture
def serve(monkeypatch):
    monkeypatch.setenv("GEOMIND_MCP_TIMEOUT", "5")

    def start(**options) -> FakeMcpServer:
        server = FakeMcpServer(**options)
        monkeypatch.setattr(mcp, "TRANSPORT", server.transport())
        return server

    return start


def by_name(check: dict) -> dict[str, dict]:
    return {step["name"]: step for step in check["steps"]}


def test_the_backend_server_dict_becomes_a_geomind_record() -> None:
    record = mcp.server_record(SERVER)

    assert isinstance(record, gd.mcp.Server)
    assert (record.name, record.transport) == ("wells", "http")
    assert record.headers == {"Authorization": "Bearer s3cret"}
    assert "s3cret" not in repr(record)


async def test_a_healthy_server_passes_every_step_with_its_tools(serve) -> None:
    server = serve(token="s3cret")

    check = await mcp.check_server(SERVER)

    assert check["ok"] is True and check["code"] is None
    assert [step["name"] for step in check["steps"]] == list(mcp.STEPS)
    assert {step["status"] for step in check["steps"]} == {"ok"}
    assert check["tools"] == [
        {"name": "search", "description": "Find a well", "read_only": True},
        {"name": "write", "description": "Write a note", "read_only": False},
    ]
    assert check["server"] == {"name": None, "version": None, "protocol": None}
    assert check["elapsed_ms"] >= 0
    assert server.seen[0]["authorization"] == "Bearer s3cret"


async def test_refused_credentials_fail_initialize_and_auth(serve) -> None:
    serve(token="other")

    check = await mcp.check_server(SERVER)

    steps = by_name(check)
    assert check["code"] == "auth_refused"
    assert steps["reachable"]["status"] == "ok"
    assert steps["auth"] == {
        "name": "auth",
        "status": "failed",
        "reason": "The server refused the credentials",
    }
    assert steps["tools"]["status"] == "skipped"


async def test_a_server_that_does_not_answer_is_unreachable(serve) -> None:
    serve(down=True)

    check = await mcp.check_server(SERVER)

    steps = by_name(check)
    assert check["code"] == "unreachable"
    assert steps["reachable"]["reason"] == (
        "The server could not be reached at this address"
    )
    assert steps["initialize"]["status"] == "skipped"


async def test_an_http_error_on_initialize_names_the_status(serve) -> None:
    serve(fail="initialize", status=404)

    check = await mcp.check_server(SERVER)

    steps = by_name(check)
    assert steps["reachable"]["status"] == "ok"
    assert steps["initialize"]["reason"] == "The server answered HTTP 404"
    assert check["reason"] == "The server answered HTTP 404"


async def test_a_server_error_text_never_shows_a_header_value(serve) -> None:
    serve(error="bad token s3cret")
    server = {**SERVER, "headers": {"Authorization": "s3cret"}}

    check = await mcp.check_server(server)

    tools = by_name(check)["tools"]
    assert tools["status"] == "failed"
    assert "s3cret" not in tools["reason"]
    assert by_name(check)["auth"]["status"] == "ok"


async def test_refused_arguments_keep_geomind_code_and_hide_header_values(
    serve,
) -> None:
    serve(error="cursor must be text, not s3cret", error_code=-32602)
    server = {**SERVER, "headers": {"Authorization": "s3cret"}}

    check = await mcp.check_server(server)

    tools = by_name(check)["tools"]
    assert check["code"] == "invalid_arguments"
    assert tools["status"] == "failed"
    assert tools["reason"].startswith("The server refused the arguments")
    assert "s3cret" not in tools["reason"]
    assert by_name(check)["auth"]["status"] == "ok"


async def test_another_server_error_stays_a_bad_response(serve) -> None:
    serve(error="something broke")

    check = await mcp.check_server(SERVER)

    assert check["code"] == "bad_response"
    assert by_name(check)["tools"]["reason"] == (
        "The server answered with an error: something broke"
    )


async def test_an_invalid_server_or_missing_timeout_is_a_readable_failure(
    serve, monkeypatch
) -> None:
    serve()
    invalid = await mcp.check_server({**SERVER, "name": "Not A Name"})
    monkeypatch.delenv("GEOMIND_MCP_TIMEOUT")
    untimed = await mcp.check_server(SERVER)

    assert invalid["code"] == "bad_settings"
    assert "name" in invalid["reason"]
    assert untimed["code"] == "bad_settings"
    assert "GEOMIND_MCP_TIMEOUT" in untimed["reason"]


async def test_an_unexpected_failure_is_not_shown_as_python_text(
    serve, monkeypatch
) -> None:
    serve()

    async def broken(*_args):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(mcp, "run_check", broken)

    check = await mcp.check_server(SERVER)

    assert check["reason"] == "The check failed in an unexpected way"
    assert "internals" not in str(check)


def test_without_geomind_mcp_the_check_is_not_implemented(monkeypatch) -> None:
    monkeypatch.delattr(gd, "mcp", raising=False)

    with pytest.raises(Exception) as raised:
        mcp.server_record(SERVER)

    assert getattr(raised.value, "code", None) == "not_implemented"
