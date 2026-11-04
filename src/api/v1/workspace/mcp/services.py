from typing import Any
from uuid import UUID

from src.api.v1.workspace.mcp import schemas
from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.models.mcp_server import McpServer
from src.core.clients.postgres.repositories.mcp_server import McpServerRepository
from src.core.errors import AppError, NotFoundError, ValidationFailedError
from src.core.geomind import mcp
from src.core.mcp_servers import server_of
from src.core.secrets import seal

NO_CLIENT = "geomind has no MCP client yet; the server is checked once it has"


class McpServerNotFoundError(NotFoundError):
    code = "mcp_server_not_found"


def to_server(
    server: McpServer, check: dict[str, Any] | None = None
) -> schemas.McpServer:
    found = check or {}
    return schemas.McpServer(
        id=server.id,
        name=server.name,
        url=server.url,
        transport=server.transport,
        auth=server.auth,
        header_name=server.header_name,
        has_secret=server.secret is not None,
        enabled=server.enabled,
        status=server.status,
        error=server.error,
        checked=server.checked,
        tools=server.tools,
        created=server.created,
        steps=found.get("steps"),
        server_info=found.get("server"),
        elapsed_ms=found.get("elapsed_ms"),
    )


def check_auth(values: dict[str, Any]) -> None:
    auth = values.get("auth")
    if auth == "header" and not values.get("header_name"):
        raise ValidationFailedError({"header_name": "A header server names its header"})
    if auth in ("bearer", "header") and not values.get("secret"):
        raise ValidationFailedError({"secret": "This sign-in needs a secret"})


async def require_server(server_id: UUID, repository: McpServerRepository) -> McpServer:
    server = await repository.get_by_id(server_id)
    if server is None:
        raise McpServerNotFoundError("MCP server not found")
    return server


async def require_free_name(
    name: str, repository: McpServerRepository, own: UUID | None = None
) -> None:
    found = await repository.get_by_name(name)
    if found is not None and found.id != own:
        raise ValidationFailedError({"name": "Another server has this name"})


async def check_server(
    server: McpServer, repository: McpServerRepository
) -> schemas.McpServer:
    """Check the server in one round trip through geomind and keep what it said.

    The answer has each step of the check; the row keeps the status, the tools and
    the first failure as ``"<code>: <reason>"``.
    """
    try:
        check = await mcp.check_server(server_of(server))
    except AppError as error:
        if error.code != "not_implemented":
            raise
        values = {"status": "unchecked", "error": NO_CLIENT}
        saved = await repository.update(server, {**values, "checked": utc_now()})
        return to_server(saved)
    if check["ok"]:
        values = {"status": "ok", "error": None, "tools": check["tools"]}
    else:
        reason = f"{check['code']}: {check['reason']}"
        values = {"status": "error", "error": reason, "tools": check["tools"]}
    saved = await repository.update(server, {**values, "checked": utc_now()})
    return to_server(saved, check)


async def list_servers(repository: McpServerRepository) -> list[schemas.McpServer]:
    return [to_server(item) for item in await repository.list_all()]


async def create_server(
    payload: schemas.McpServerCreate, repository: McpServerRepository
) -> schemas.McpServer:
    values = payload.model_dump()
    check_auth(values)
    await require_free_name(payload.name, repository)
    values["url"] = str(payload.url)
    values["secret"] = None if payload.secret is None else seal(payload.secret)
    server = await repository.create(values)
    return await check_server(server, repository)


async def update_server(
    server_id: UUID,
    payload: schemas.McpServerUpdate,
    repository: McpServerRepository,
) -> schemas.McpServer:
    server = await require_server(server_id, repository)
    change = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in change:
        await require_free_name(change["name"], repository, server.id)
    if "url" in change:
        change["url"] = str(payload.url)
    merged = {
        "auth": change.get("auth", server.auth),
        "header_name": change.get("header_name", server.header_name),
        "secret": change.get("secret") or server.secret,
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
    return to_server(await repository.update(server, change))


async def delete_server(server_id: UUID, repository: McpServerRepository) -> None:
    await repository.delete(await require_server(server_id, repository))
