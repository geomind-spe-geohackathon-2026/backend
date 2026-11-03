from typing import Any

from src.core.clients.postgres.models.connector import Connector
from src.core.secrets import unseal


def headers_of(connector: Connector) -> dict[str, str]:
    """Return the headers that carry a connector's secret; none when it has none."""
    secret = None if connector.secret is None else unseal(connector.secret)
    if secret is None or connector.auth == "none":
        return {}
    if connector.auth == "bearer":
        return {"Authorization": f"Bearer {secret}"}
    return {str(connector.header_name): secret}


def server_of(connector: Connector) -> dict[str, Any]:
    """Return a connector in the shape geomind's MCP client and workspace take."""
    return {
        "name": connector.name,
        "url": connector.url,
        "transport": connector.transport,
        "headers": headers_of(connector),
    }
