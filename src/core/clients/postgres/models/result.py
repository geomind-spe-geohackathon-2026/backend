from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now


class Result(Base):
    """The result of a study: a summary for lists and gemini's content for detail."""

    __tablename__ = "results"
    __table_args__ = (
        Index("ix_results_project_id_created_id", "project_id", "created", "id"),
        Index("ix_results_study_id", "study_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    study_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("studies.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(String(255))
    case_version: Mapped[int | None]
    plant_version: Mapped[int | None]
    summary: Mapped[dict[str, Any]] = mapped_column(Json)
    content: Mapped[dict[str, Any]] = mapped_column(Json)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
