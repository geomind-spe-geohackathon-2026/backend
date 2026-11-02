from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from src.core.assistant.schemas import Chat, Run
from src.core.progress.schemas import Progress


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
