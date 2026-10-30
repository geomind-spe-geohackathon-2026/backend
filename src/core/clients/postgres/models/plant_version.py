from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, UtcDateTime, utc_now


class PlantVersion(Base):
    """One saved plant, exactly as gemini's to_dict writes it. Never updated."""

    __tablename__ = "plant_versions"
    __table_args__ = (UniqueConstraint("project_id", "number"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    number: Mapped[int]
    plant_type: Mapped[str] = mapped_column(Text)
    content: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
    )
    digest: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
