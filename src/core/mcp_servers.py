from typing import Any

from src.core.clients.postgres.models.mcp_server import McpServer
from src.core.secrets import unseal


def headers_of(server: McpServer) -> dict[str, str]:
    """Return the headers that carry a server's secret; none when it has none."""
    secret = None if server.secret is None else unseal(server.secret)
    if secret is None or server.auth == "none":
        return {}
    if server.auth == "bearer":
        return {"Authorization": f"Bearer {secret}"}
    return {str(server.header_name): secret}


def server_of(server: McpServer) -> dict[str, Any]:
    """Return a server in the shape geomind's MCP client and workspace take."""
    return {
        "name": server.name,
        "url": server.url,
        "transport": server.transport,
        "headers": headers_of(server),
    }
