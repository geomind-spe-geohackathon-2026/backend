from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now

StudyStatus = Literal["queued", "running", "done", "failed", "cancelled", "blocked"]
ACTIVE_STUDY_STATUSES = ("queued", "running")


class Study(Base):
    """A calculation of one project, run as a Celery job. Progress lives in Redis."""

    __tablename__ = "studies"
    __table_args__ = (
        Index("ix_studies_project_id_created_id", "project_id", "created", "id"),
        Index("ix_studies_project_id_status", "project_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    kind: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    settings: Mapped[dict[str, Any]] = mapped_column(Json)
    status: Mapped[str] = mapped_column(String(16))
    progress_done: Mapped[int] = mapped_column(default=0)
    progress_total: Mapped[int] = mapped_column(default=1)
    started_by_kind: Mapped[str] = mapped_column(String(16))
    started_by_name: Mapped[str] = mapped_column(String(255))
    started_by_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"),
    )
    case_version: Mapped[int | None]
    plant_version: Mapped[int | None]
    plant_pinned: Mapped[bool] = mapped_column(default=False, server_default=false())
    missing: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    error: Mapped[dict[str, Any] | None] = mapped_column(Json)
    task_id: Mapped[str | None] = mapped_column(Text)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    started: Mapped[datetime | None] = mapped_column(UtcDateTime)
    ended: Mapped[datetime | None] = mapped_column(UtcDateTime)
