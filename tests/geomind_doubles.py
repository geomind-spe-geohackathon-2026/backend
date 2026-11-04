"""A fake MCP server behind an httpx mock transport, for geomind's real MCP client."""

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

TOOLS = [
    {
        "name": "search",
        "description": "Find a well",
        "annotations": {"readOnlyHint": True},
        "inputSchema": {"type": "object", "properties": {}},
    },
    {"name": "write", "description": "Write a note"},
]


@dataclass
class FakeMcpServer:
    """Answer ``initialize`` and ``tools/list`` like a streamable HTTP MCP server.

    ``token`` is the bearer it takes (``None`` takes any request); ``fail`` names a
    method that answers ``status`` instead; ``down`` makes every request fail to
    connect. ``error`` makes ``tools/list`` answer a JSON-RPC error of that text,
    with the code ``error_code``. ``seen`` keeps the headers of each request.
    """

    tools: list[dict[str, Any]] = field(default_factory=lambda: list(TOOLS))
    token: str | None = None
    fail: str | None = None
    status: int = 500
    down: bool = False
    error: str | None = None
    error_code: int = -32000
    seen: list[dict[str, str]] = field(default_factory=list)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(dict(request.headers))
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        body = json.loads(request.content)
        method = body.get("method")
        if self.token is not None:
            given = request.headers.get("authorization")
            if given != f"Bearer {self.token}":
                return httpx.Response(401, json={"error": "unauthorized"})
        if method == self.fail:
            return httpx.Response(self.status, text="failed")
        if "id" not in body:
            return httpx.Response(202)
        if method == self.fail_with_error():
            error = {"code": self.error_code, "message": self.error}
            answer = {"jsonrpc": "2.0", "id": body["id"], "error": error}
            return httpx.Response(200, json=answer)
        return httpx.Response(200, json=self.answer(body))

    def fail_with_error(self) -> str | None:
        return "tools/list" if self.error is not None else None

    def answer(self, body: dict[str, Any]) -> dict[str, Any]:
        if body["method"] == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "1.0"},
            }
        else:
            result = {"tools": self.tools}
        return {"jsonrpc": "2.0", "id": body["id"], "result": result}
