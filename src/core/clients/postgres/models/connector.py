from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now


class Connector(Base):
    """An MCP server the agents may use; ``secret`` is sealed and never sent out."""

    __tablename__ = "connectors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    url: Mapped[str] = mapped_column(Text)
    transport: Mapped[str] = mapped_column(String(8))
    auth: Mapped[str] = mapped_column(String(8))
    header_name: Mapped[str | None] = mapped_column(String(255))
    secret: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="unchecked")
    error: Mapped[str | None] = mapped_column(Text)
    checked: Mapped[datetime | None] = mapped_column(UtcDateTime)
    tools: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utc_now, onupdate=utc_now
    )
