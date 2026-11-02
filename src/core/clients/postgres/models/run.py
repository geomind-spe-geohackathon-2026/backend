from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now

RunStatus = Literal["queued", "running", "waiting", "done", "failed", "cancelled"]
ACTIVE_RUN_STATUSES = ("queued", "running", "waiting")
FINISHED_STATUSES = ("done", "failed", "cancelled")


class Run(Base):
    """One assistant run. Its id is the run id geomind uses in its store."""

    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_project_id_created_id", "project_id", "created", "id"),
        Index("ix_runs_project_id_status", "project_id", "status"),
        Index("ix_runs_chat_id_created", "chat_id", "created"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chat_id: Mapped[UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16))
    loop: Mapped[str | None] = mapped_column(String(64))
    request: Mapped[dict[str, Any] | None] = mapped_column(Json)
    error: Mapped[dict[str, Any] | None] = mapped_column(Json)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost: Mapped[float] = mapped_column(default=0.0)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    started: Mapped[datetime | None] = mapped_column(UtcDateTime)
    ended: Mapped[datetime | None] = mapped_column(UtcDateTime)
