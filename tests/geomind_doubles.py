"""Stand-ins for the parts of geomind the backend uses before geomind ships them."""

from types import SimpleNamespace

import geomind as gd


class ConnectorError(gd.errors.GeomindError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def mcp_with(tools: list[dict] | None = None, error: str | None = None, seen=None):
    def list_tools(server: dict) -> list[dict]:
        if seen is not None:
            seen.append(server)
        if error is not None:
            raise ConnectorError("the server refused the sign-in", error)
        return tools or []

    return SimpleNamespace(list_tools=list_tools, ConnectorError=ConnectorError)
