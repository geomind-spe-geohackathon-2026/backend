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
    plant_version: int | None = Field(default=None, ge=1)


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
    plant_pinned: bool
    result: UUID | None
    error: StudyError | None
    missing: list[Missing]
    created: datetime
    ended: datetime | None


class StudyStructure(BaseModel):
    rank: int
    structure: dict[str, Any]
    evaluations: int | None
    feasible_evaluations: int | None
    feasible: bool
    reason: Any
    violation: float | None
    metrics: dict[str, Any]
    parameters: dict[str, Any]
    on_front: bool


class StudyStructures(BaseModel):
    study: UUID
    name: str
    objectives: list[Any]
    budget: dict[str, Any]
    total: int
    structures: list[StudyStructure]


class StructurePlant(BaseModel):
    rank: int
    structure: dict[str, Any]
    plant: dict[str, Any]


class SavedStructurePlant(BaseModel):
    rank: int
    plant_version: int
