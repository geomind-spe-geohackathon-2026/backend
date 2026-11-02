from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now


class RunArtifact(Base):
    """A value saved under a key: bytes or JSON, in the space of a run or of a chat.

    A run's artifact holds its run and its chat and is read by ``(run_id, key)``.
    A chat's artifact has no run (``run_id`` is null) and is read by
    ``(chat_id, key, created)``; the two spaces are separate.
    """

    __tablename__ = "run_artifacts"
    __table_args__ = (
        Index("ix_run_artifacts_run_id_key", "run_id", "key"),
        Index("ix_run_artifacts_chat_id_key_created", "chat_id", "key", "created"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE")
    )
    chat_id: Mapped[UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(8))
    data_bytes: Mapped[bytes | None] = mapped_column(LargeBinary)
    data_json: Mapped[Any | None] = mapped_column(Json)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    @property
    def data(self) -> Any:
        """Return the saved bytes or JSON value."""
        return self.data_bytes if self.kind == "bytes" else self.data_json
