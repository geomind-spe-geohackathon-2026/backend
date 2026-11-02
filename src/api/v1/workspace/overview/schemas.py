from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from src.core.progress.schemas import Progress


class ChatRun(BaseModel):
    id: UUID
    status: str


class Chat(BaseModel):
    id: UUID
    project: UUID
    title: str
    created: datetime
    last_run: ChatRun | None


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cost: float


class RunError(BaseModel):
    code: str
    message: str


class Run(BaseModel):
    id: UUID
    chat: UUID
    project: UUID
    status: str
    loop: str | None
    started: datetime | None
    ended: datetime | None
    usage: Usage
    request: dict[str, Any] | None
    error: RunError | None


class Actor(BaseModel):
    kind: Literal["user", "agent"]
    name: str


class Link(BaseModel):
    route: str
    id: str | None


class Activity(BaseModel):
    id: UUID
    time: datetime
    actor: Actor
    text: str
    link: Link | None


class Overview(BaseModel):
    progress: Progress
    chats: list[Chat]
    activity: list[Activity]
    active_runs: list[Run]
