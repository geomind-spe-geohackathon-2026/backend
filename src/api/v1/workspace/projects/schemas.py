from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints

from src.core.progress.schemas import Progress

ProjectName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class ProjectCreate(BaseModel):
    name: ProjectName
    case_from: UUID | None = None


class ProjectUpdate(BaseModel):
    name: ProjectName


class ProjectFile(BaseModel):
    format: Literal[1]
    name: ProjectName
    exported: AwareDatetime


class VersionFile(BaseModel):
    number: int
    note: str
    created: AwareDatetime
    content: Any


class CaseVersionFile(BaseModel):
    number: int
    note: str
    created: AwareDatetime
    content: dict[str, Any]


class Owner(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class Project(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner: Owner
    plant_version: int | None
    case_version: int | None
    created: datetime
    updated: datetime
    progress: Progress
    chats: int
    runs: int
