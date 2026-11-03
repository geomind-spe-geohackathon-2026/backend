from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StringConstraints

McpServerName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,32}$")]
"""A server's name becomes part of its tools' names: ``<name>__<tool>``."""
HeaderName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{1,255}$")]
Transport = Literal["http", "sse"]
Auth = Literal["none", "bearer", "header"]
Status = Literal["unchecked", "ok", "error"]


class McpServerCreate(BaseModel):
    name: McpServerName
    url: AnyHttpUrl
    transport: Transport = "http"
    auth: Auth = "none"
    header_name: HeaderName | None = None
    secret: str | None = Field(default=None, min_length=1, max_length=4096)


class McpServerUpdate(BaseModel):
    name: McpServerName | None = None
    url: AnyHttpUrl | None = None
    transport: Transport | None = None
    auth: Auth | None = None
    header_name: HeaderName | None = None
    secret: str | None = Field(default=None, min_length=1, max_length=4096)
    enabled: bool | None = None


class McpTool(BaseModel):
    name: str
    description: str
    read_only: bool


class McpServer(BaseModel):
    """An MCP server as anyone may see it: the secret is only ``has_secret``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url: str
    transport: Transport
    auth: Auth
    header_name: str | None
    has_secret: bool
    enabled: bool
    status: Status
    error: str | None
    checked: datetime | None
    tools: list[McpTool]
    created: datetime
