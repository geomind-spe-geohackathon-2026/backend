from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now


class MemoryEntry(Base):
    """One entry of the agents' own memory, as geomind writes it.

    Only geomind writes it: role lessons and designs that passed review, in the
    ``experience`` section. Experience is shared by every project, so the team learns;
    ``data`` is kept exactly as given, its ``origin`` and ``project_id`` included.
    ``project_id`` is set only for an entry geomind marks as a project's own.
    """

    __tablename__ = "memory_entries"
    __table_args__ = (
        UniqueConstraint(
            "section", "project_id", "entry_id", name="uq_memory_entries_entry"
        ),
        Index("ix_memory_entries_section_created_id", "section", "created", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    section: Mapped[str] = mapped_column(String(16))
    entry_id: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(Json)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    created_by_kind: Mapped[str] = mapped_column(String(16))
    created_by: Mapped[str | None] = mapped_column(Text)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utc_now, onupdate=utc_now
    )
