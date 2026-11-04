"""The health check of an MCP server, through geomind's own MCP client.

The check uses only what ``gd.mcp`` offers publicly: ``Server``, ``McpClient`` and
``McpError``. It is the client geomind's agents use, so a check sees what a run sees.
"""

import re
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import geomind as gd
import httpx
import pydantic

from src.core.errors import NotImplementedYetError

REACHABLE = "reachable"
INITIALIZE = "initialize"
AUTH = "auth"
TOOLS = "tools"
STEPS = (REACHABLE, INITIALIZE, AUTH, TOOLS)
OK = "ok"
FAILED = "failed"
SKIPPED = "skipped"
UNREACHABLE = "unreachable"
AUTH_REFUSED = "auth_refused"
BAD_RESPONSE = "bad_response"
BAD_SETTINGS = "bad_settings"
INVALID_ARGUMENTS = "invalid_arguments"
HTTP_STATUS = re.compile(r"\bHTTP (\d{3})\b")
CLASS_NAME = re.compile(r"^\(?[A-Z][A-Za-z0-9_]*\)?$")
REASON_LENGTH = 300
HIDDEN = "***"
TRANSPORT: httpx.AsyncBaseTransport | None = None
"""The httpx transport geomind's client sends through; ``None`` is the network.

Tests set a mock transport here, so no check reaches a real server.
"""


@dataclass
class Check:
    """What one check found: each step, the tools, the first failure and the time."""

    steps: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            name: {"name": name, "status": SKIPPED, "reason": None} for name in STEPS
        }
    )
    tools: list[dict[str, Any]] = field(default_factory=list)
    code: str | None = None
    reason: str | None = None
    elapsed_ms: int = 0
    server: dict[str, Any] = field(
        default_factory=lambda: {"name": None, "version": None, "protocol": None}
    )

    @property
    def ok(self) -> bool:
        return self.code is None

    def passed(self, *names: str) -> None:
        for name in names:
            self.steps[name].update(status=OK, reason=None)

    def failed(self, name: str, code: str, reason: str) -> None:
        self.steps[name].update(status=FAILED, reason=reason)
        if self.code is None:
            self.code, self.reason = code, reason

    def result(self) -> dict[str, Any]:
        """Return the check as plain data, its ``steps`` in order."""
        return {
            "ok": self.ok,
            "code": self.code,
            "reason": self.reason,
            "steps": [self.steps[name] for name in STEPS],
            "server": self.server,
            "tools": self.tools,
            "elapsed_ms": self.elapsed_ms,
        }


def client_module() -> Any:
    mcp = getattr(gd, "mcp", None)
    if mcp is None or not hasattr(mcp, "McpClient"):
        raise NotImplementedYetError("geomind MCP client (gd.mcp)")
    return mcp


def server_record(server: dict[str, Any]) -> Any:
    """Return geomind's ``Server`` record of ``{name, url, transport, headers}``."""
    return client_module().Server.model_validate(server)


def timeout_of() -> float | None:
    """Return geomind's ``mcp_timeout`` in seconds, or ``None`` when it is not set."""
    value = gd.runtime.get("mcp_timeout")
    return None if value is None else float(value)


def hidden(text: str, headers: dict[str, str]) -> str:
    """Return ``text`` without any header value, cut to a readable length."""
    for value in headers.values():
        if value:
            text = text.replace(value, HIDDEN)
    return text[:REASON_LENGTH]


def detail_of(error: Exception, name: str) -> str:
    """Return geomind's message without the server name it starts with."""
    text = str(error).strip()
    prefix = f"{name}:"
    return text[len(prefix) :].strip() if text.startswith(prefix) else text


def unreachable_reason(detail: str, timeout: float) -> str:
    if "Timeout" in detail:
        return f"The server did not answer within {timeout:g} s"
    return "The server could not be reached at this address"


def response_reason(detail: str, headers: dict[str, str]) -> str:
    """Return a readable reason for an answer that is not what MCP expects."""
    status = HTTP_STATUS.search(detail)
    if status is not None:
        return f"The server answered HTTP {status.group(1)}"
    if not detail or CLASS_NAME.match(detail):
        return "The server's answer is not a valid MCP answer"
    if detail.startswith("no answer to request") or "stream ended" in detail:
        return "The server sent no answer to the request"
    return f"The server answered with an error: {hidden(detail, headers)}"


def arguments_reason(detail: str, headers: dict[str, str]) -> str:
    """Return a readable reason for a request whose arguments the server refused."""
    if not detail or CLASS_NAME.match(detail):
        return "The server refused the arguments of the request"
    return f"The server refused the arguments of the request: {hidden(detail, headers)}"


def refused(check: Check, step: str, error: Exception, server: Any) -> None:
    """Mark ``step`` failed with the code geomind gave, ``bad_response`` by default."""
    detail = detail_of(error, server.name)
    if getattr(error, "code", None) == INVALID_ARGUMENTS:
        reason = arguments_reason(detail, server.headers)
        check.failed(step, INVALID_ARGUMENTS, reason)
        return
    check.failed(step, BAD_RESPONSE, response_reason(detail, server.headers))


def tool_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": str(item.get("name") or ""),
            "description": str(item.get("description") or ""),
            "read_only": bool(item.get("read_only")),
        }
        for item in rows
    ]


def opening_failed(check: Check, error: Exception, server: Any, timeout: float) -> None:
    """Mark the steps of a failure before ``initialize`` was answered."""
    code = getattr(error, "code", None)
    detail = detail_of(error, server.name)
    if code == UNREACHABLE:
        check.failed(REACHABLE, UNREACHABLE, unreachable_reason(detail, timeout))
        return
    check.passed(REACHABLE)
    if code == AUTH_REFUSED:
        reason = "The server refused the credentials"
        check.failed(INITIALIZE, AUTH_REFUSED, reason)
        check.failed(AUTH, AUTH_REFUSED, reason)
        return
    refused(check, INITIALIZE, error, server)


def listing_failed(check: Check, error: Exception, server: Any) -> None:
    """Mark the steps of a failure of ``tools/list`` after ``initialize``."""
    code = getattr(error, "code", None)
    if code == AUTH_REFUSED:
        check.failed(AUTH, AUTH_REFUSED, "The server refused the credentials")
        return
    check.passed(AUTH)
    if code == UNREACHABLE:
        reason = "The server stopped answering while it listed its tools"
        check.failed(TOOLS, UNREACHABLE, reason)
        return
    refused(check, TOOLS, error, server)


async def run_check(check: Check, server: Any, timeout: float) -> None:
    mcp = client_module()
    opened = False
    try:
        async with mcp.McpClient(server, timeout, TRANSPORT) as client:
            opened = True
            check.passed(REACHABLE, INITIALIZE)
            try:
                rows = await client.list_tools()
            except mcp.McpError as error:
                listing_failed(check, error, server)
                return
            check.passed(AUTH, TOOLS)
            check.tools = tool_rows(rows)
    except mcp.McpError as error:
        if opened:
            raise
        opening_failed(check, error, server, timeout)


async def check_server(server: dict[str, Any]) -> dict[str, Any]:
    """Check an MCP server in one round trip and return what each step found.

    ``server`` is ``{name, url, transport, headers}``. The steps are ``reachable``,
    ``initialize``, ``auth`` and ``tools``, each ``ok``, ``failed`` or ``skipped``
    with a readable reason; a reason never holds a header value or a Python error.
    geomind's client does not hand out the ``initialize`` answer, so ``server``
    (name, version, protocol) stays ``None``. Raises ``not_implemented`` when geomind
    has no MCP client.
    """
    client_module()
    check = Check()
    started = perf_counter()
    try:
        await checked(check, server)
    finally:
        check.elapsed_ms = round((perf_counter() - started) * 1000)
    return check.result()


async def checked(check: Check, server: dict[str, Any]) -> None:
    try:
        record = server_record(server)
    except pydantic.ValidationError:
        reason = "The connector's name, address or transport is not valid"
        check.failed(REACHABLE, BAD_SETTINGS, reason)
        return
    timeout = timeout_of()
    if timeout is None:
        reason = "GEOMIND_MCP_TIMEOUT is not set, so no server can be checked"
        check.failed(REACHABLE, BAD_SETTINGS, reason)
        return
    try:
        await run_check(check, record, timeout)
    except Exception:
        failed = next(
            (name for name in STEPS if check.steps[name]["status"] != OK), TOOLS
        )
        check.failed(failed, BAD_RESPONSE, "The check failed in an unexpected way")
