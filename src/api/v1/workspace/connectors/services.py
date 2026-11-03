import asyncio
from typing import Any
from uuid import UUID

from src.api.v1.workspace.connectors import schemas
from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.models.connector import Connector
from src.core.clients.postgres.repositories.connector import ConnectorRepository
from src.core.connectors import server_of
from src.core.errors import AppError, NotFoundError, ValidationFailedError
from src.core.geomind import mcp
from src.core.secrets import seal

NO_CLIENT = "geomind has no MCP client yet; the connector is checked once it has"


class ConnectorNotFoundError(NotFoundError):
    code = "connector_not_found"


def to_connector(connector: Connector) -> schemas.Connector:
    return schemas.Connector(
        id=connector.id,
        name=connector.name,
        url=connector.url,
        transport=connector.transport,
        auth=connector.auth,
        header_name=connector.header_name,
        has_secret=connector.secret is not None,
        enabled=connector.enabled,
        status=connector.status,
        error=connector.error,
        checked=connector.checked,
        tools=connector.tools,
        created=connector.created,
    )


def check_auth(values: dict[str, Any]) -> None:
    auth = values.get("auth")
    if auth == "header" and not values.get("header_name"):
        raise ValidationFailedError(
            {"header_name": "A header connector names its header"}
        )
    if auth in ("bearer", "header") and not values.get("secret"):
        raise ValidationFailedError({"secret": "This sign-in needs a secret"})


async def require_connector(
    connector_id: UUID, repository: ConnectorRepository
) -> Connector:
    connector = await repository.get_by_id(connector_id)
    if connector is None:
        raise ConnectorNotFoundError("Connector not found")
    return connector


async def require_free_name(
    name: str, repository: ConnectorRepository, own: UUID | None = None
) -> None:
    found = await repository.get_by_name(name)
    if found is not None and found.id != own:
        raise ValidationFailedError({"name": "Another connector has this name"})


async def check_connector(
    connector: Connector, repository: ConnectorRepository
) -> schemas.Connector:
    """Ask the server for its tools through geomind and keep what it said."""
    try:
        tools = await asyncio.to_thread(mcp.list_tools, server_of(connector))
        values = {"status": "ok", "error": None, "tools": tools}
    except AppError as error:
        if error.code != "not_implemented":
            raise
        values = {"status": "unchecked", "error": NO_CLIENT}
    except Exception as error:
        code = getattr(error, "code", None)
        reason = f"{code}: {error}" if code else str(error)
        values = {"status": "error", "error": reason, "tools": []}
    saved = await repository.update(connector, {**values, "checked": utc_now()})
    return to_connector(saved)


async def list_connectors(repository: ConnectorRepository) -> list[schemas.Connector]:
    return [to_connector(item) for item in await repository.list_all()]


async def create_connector(
    payload: schemas.ConnectorCreate, repository: ConnectorRepository
) -> schemas.Connector:
    values = payload.model_dump()
    check_auth(values)
    await require_free_name(payload.name, repository)
    values["url"] = str(payload.url)
    values["secret"] = None if payload.secret is None else seal(payload.secret)
    connector = await repository.create(values)
    return await check_connector(connector, repository)


async def update_connector(
    connector_id: UUID,
    payload: schemas.ConnectorUpdate,
    repository: ConnectorRepository,
) -> schemas.Connector:
    connector = await require_connector(connector_id, repository)
    change = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in change:
        await require_free_name(change["name"], repository, connector.id)
    if "url" in change:
        change["url"] = str(payload.url)
    merged = {
        "auth": change.get("auth", connector.auth),
        "header_name": change.get("header_name", connector.header_name),
        "secret": change.get("secret") or connector.secret,
    }
    check_auth(merged)
    if "secret" in change:
        change["secret"] = seal(change["secret"])
    if merged["auth"] == "none":
        change["secret"] = None
    reaches = {"url", "transport", "auth", "header_name", "secret"} & set(change)
    if reaches:
        change.update(
            {"status": "unchecked", "error": None, "tools": [], "checked": None}
        )
    return to_connector(await repository.update(connector, change))


async def delete_connector(connector_id: UUID, repository: ConnectorRepository) -> None:
    await repository.delete(await require_connector(connector_id, repository))
