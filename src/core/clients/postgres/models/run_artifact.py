from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now


class RunArtifact(Base):
    """A value a run saved under a key: bytes or JSON.

    A row holds both the run and its chat, so the run reads its own artifacts by
    ``(run_id, key)`` and the next message of the chat reads the newest one by
    ``(chat_id, key, created)``.
    """

    __tablename__ = "run_artifacts"
    __table_args__ = (
        Index("ix_run_artifacts_run_id_key", "run_id", "key"),
        Index("ix_run_artifacts_chat_id_key_created", "chat_id", "key", "created"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
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
