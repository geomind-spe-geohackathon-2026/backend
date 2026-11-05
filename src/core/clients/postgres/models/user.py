from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, UtcDateTime, utc_now

Role = Literal["admin", "member"]


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="member")
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    tokens_valid_after: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    auto_approve: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    """The user's answer for new chats' auto-approve; ``None`` until asked once (QA-292)."""
