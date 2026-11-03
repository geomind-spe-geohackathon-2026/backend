from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now


class KnowledgeEntry(Base):
    """One entry of geomind's shared memory.

    ``data`` is the entry as geomind writes it, its own ``id`` and ``origin`` included.
    ``project_id`` is set for a project's own facts, which only that project sees; the
    catalogue, confirmed sources and experience have none and every project sees them.
    ``created_by`` is a user's id or an agent run's id, as ``created_by_kind`` says.
    """

    __tablename__ = "knowledge_entries"
    __table_args__ = (
        UniqueConstraint(
            "section", "project_id", "entry_id", name="uq_knowledge_entries_entry"
        ),
        Index("ix_knowledge_entries_section_created_id", "section", "created", "id"),
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
