from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, UtcDateTime, utc_now


class Activity(Base):
    """One line of a project's history, written by the service that made the change."""

    __tablename__ = "activity"
    __table_args__ = (
        Index("ix_activity_project_id_created_id", "project_id", "created", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    actor_kind: Mapped[str] = mapped_column(String(16))
    actor_name: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    link_route: Mapped[str | None] = mapped_column(String(64))
    link_id: Mapped[str | None] = mapped_column(String(64))
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
