from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.core.assistant.schemas import Run


class ChatCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: UUID
    title: str | None = Field(default=None, min_length=1, max_length=255)


class ChatUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)


class AutoApprove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_approve: bool


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)


class Suggestion(BaseModel):
    """A next step the user may click; ``message`` is sent as their next message."""

    label: str
    message: str


class Suggestions(BaseModel):
    suggestions: list[Suggestion]


class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat: UUID = Field(validation_alias="chat_id")
    role: Literal["user", "assistant"]
    content: str
    created: datetime
    run: UUID | None = Field(validation_alias="run_id")
    suggestions: list[Suggestion] | None = None


class MessageSent(BaseModel):
    message: Message
    run: Run


class ChatState(BaseModel):
    version: int
    state: dict[str, Any] | None
    suggestions: list[Suggestion] = []
