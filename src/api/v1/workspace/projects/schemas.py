from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints

ProjectName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class ProjectCreate(BaseModel):
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


class OwnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner: OwnerResponse
    plant_version: int | None
    created: datetime
    updated: datetime
