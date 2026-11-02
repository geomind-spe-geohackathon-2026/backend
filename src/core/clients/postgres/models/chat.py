from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, UtcDateTime, utc_now


class Chat(Base):
    """A conversation of one project with the assistant."""

    __tablename__ = "chats"
    __table_args__ = (
        Index("ix_chats_project_id_created_id", "project_id", "created", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    title: Mapped[str] = mapped_column(String(255))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=utc_now,
        onupdate=utc_now,
    )
