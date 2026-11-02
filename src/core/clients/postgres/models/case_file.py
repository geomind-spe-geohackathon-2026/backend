from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, UtcDateTime, utc_now


class CaseFile(Base):
    """A file that one case version names; its bytes live in MinIO."""

    __tablename__ = "case_files"
    __table_args__ = (UniqueConstraint("case_version_id", "name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    case_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("case_versions.id", ondelete="CASCADE"),
    )
    name: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger)
    object_key: Mapped[str] = mapped_column(Text)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
