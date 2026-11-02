from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.clients.postgres.client import Base, Json


class RunEvent(Base):
    """One event of a run's log; ``data`` is geomind's full ``event.to_dict()``."""

    __tablename__ = "run_events"
    __table_args__ = (Index("ix_run_events_run_id_sequence", "run_id", "sequence"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    sequence: Mapped[int]
    type: Mapped[str] = mapped_column(String(64))
    public: Mapped[bool]
    data: Mapped[dict[str, Any]] = mapped_column(Json)
