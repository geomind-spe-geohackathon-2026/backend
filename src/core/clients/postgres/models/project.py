from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from src.core.clients.postgres.client import Base, Json, UtcDateTime, utc_now
from src.core.clients.postgres.models.user import User


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=utc_now,
        onupdate=utc_now,
    )

    budget_max_tokens: Mapped[int | None] = mapped_column(BigInteger)
    budget_max_cost: Mapped[float | None] = mapped_column(Float)
    memory: Mapped[str | None] = mapped_column(String(3))
    mcp: Mapped[list[str]] = mapped_column(Json, default=list)

    owner: Mapped[User] = relationship(lazy="joined")
    plant_version: Mapped[int | None] = query_expression()
