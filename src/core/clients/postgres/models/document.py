from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, UtcDateTime, utc_now


class Document(Base):
    """A file a user uploaded to a project; its bytes live in MinIO."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_project_id_created_id", "project_id", "created", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    name: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger)
    object_key: Mapped[str] = mapped_column(Text)
    searchable: Mapped[str] = mapped_column(String(16))
    text: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
