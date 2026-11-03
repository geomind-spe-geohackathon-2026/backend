from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class Document(BaseModel):
    id: UUID
    project: UUID | None
    name: str
    size: int
    searchable: Literal["pending", "ready", "failed"]
    created: datetime
