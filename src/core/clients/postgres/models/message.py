from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now


class Message(Base):
    """One user or assistant message of a chat."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_id_created_id", "chat_id", "created", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chat_id: Mapped[UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL")
    )
    suggestions: Mapped[list[dict[str, str]] | None] = mapped_column(Json)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
