from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from src.core.clients.postgres.models import chat as chat_model
from src.core.clients.postgres.models import run as run_model

RunStatus = Literal["queued", "running", "waiting", "done", "failed", "cancelled"]


class Tokens(BaseModel):
    input_tokens: int
    output_tokens: int
    cost: float


class Failure(BaseModel):
    code: str
    message: str


class LastRun(BaseModel):
    id: UUID
    status: RunStatus


class Chat(BaseModel):
    id: UUID
    project: UUID
    title: str
    created: datetime
    last_run: LastRun | None


def to_chat(chat: chat_model.Chat, last: run_model.Run | None) -> Chat:
    """Describe a chat row with the status of its latest run."""
    last_run = None if last is None else LastRun(id=last.id, status=last.status)
    return Chat(
        id=chat.id,
        project=chat.project_id,
        title=chat.title,
        created=chat.created,
        last_run=last_run,
    )


class Run(BaseModel):
    """A run of the assistant, as the runs page and the chat show it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat: UUID
    project: UUID
    status: RunStatus
    loop: str | None
    started: datetime | None
    ended: datetime | None
    usage: Tokens
    request: dict[str, Any] | None
    error: Failure | None

    @model_validator(mode="before")
    @classmethod
    def from_row(cls, row: Any) -> Any:
        """Read a ``runs`` row: its usage columns become ``usage``."""
        if isinstance(row, dict):
            return row
        return {
            "id": row.id,
            "chat": row.chat_id,
            "project": row.project_id,
            "status": row.status,
            "loop": row.loop,
            "started": row.started,
            "ended": row.ended,
            "usage": {
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "cost": row.cost,
            },
            "request": row.request,
            "error": row.error,
        }
