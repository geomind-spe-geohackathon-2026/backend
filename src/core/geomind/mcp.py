from typing import Any

import geomind as gd

from src.core.errors import NotImplementedYetError


def list_tools(server: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the tools of an MCP server as ``[{name, description, read_only}]``.

    geomind's MCP client does the call, the one its agents use, so a check sees what a
    run will see. A failure raises geomind's error with its message.
    """
    mcp = getattr(gd, "mcp", None)
    if mcp is None:
        raise NotImplementedYetError("geomind MCP client (gd.mcp)")
    return [
        {
            "name": str(item["name"]),
            "description": str(item.get("description") or ""),
            "read_only": bool(item.get("read_only")),
        }
        for item in mcp.list_tools(server)
    ]
