from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class RagDocumentText(BaseModel):
    id: UUID
    name: str
    searchable: Literal["pending", "ready", "failed"]
    text: str | None


class RagDocument(BaseModel):
    id: UUID
    project: UUID | None
    name: str
    size: int
    searchable: Literal["pending", "ready", "failed"]
    created: datetime
