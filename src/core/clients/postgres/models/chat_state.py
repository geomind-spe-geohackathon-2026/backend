from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now


class ChatState(Base):
    """One version of the problem state of a chat, as geomind gave it."""

    __tablename__ = "chat_states"
    __table_args__ = (UniqueConstraint("chat_id", "version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chat_id: Mapped[UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    version: Mapped[int]
    state: Mapped[dict[str, Any]] = mapped_column(Json)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
