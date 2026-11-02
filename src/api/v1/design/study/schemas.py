from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

StudyStatus = Literal["queued", "running", "done", "failed", "cancelled", "blocked"]


class StudyKind(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    kind: str
    use: str
    title: str
    description: str
    schema_: dict[str, Any] = Field(alias="schema")


class StudyCreate(BaseModel):
    project: UUID
    kind: str
    name: str = Field(min_length=1, max_length=255)
    settings: dict[str, Any]


class StudyProgress(BaseModel):
    done: int
    total: int


class StartedBy(BaseModel):
    kind: Literal["user", "agent"]
    name: str
    run: UUID | None


class Missing(BaseModel):
    path: str
    message: str


class StudyError(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class Study(BaseModel):
    id: UUID
    project: UUID
    kind: str
    name: str
    settings: dict[str, Any]
    status: StudyStatus
    progress: StudyProgress
    started_by: StartedBy
    case_version: int | None
    plant_version: int | None
    result: UUID | None
    error: StudyError | None
    missing: list[Missing]
    created: datetime
    ended: datetime | None
