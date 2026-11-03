from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Section = Literal["knowledge", "experience"]


class CreatedBy(BaseModel):
    kind: Literal["seed", "user", "agent"]
    id: str | None


class Entry(BaseModel):
    """An entry as geomind keeps it, its own fields at the top level."""

    model_config = ConfigDict(extra="allow")

    id: str
    section: Section
    project: UUID | None
    created: datetime
    updated: datetime
    created_by: CreatedBy


class EntryInput(BaseModel):
    """A knowledge entry a person writes; geomind's check decides what it needs."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=255)
    project: UUID | None = None


class EntryChange(BaseModel):
    """Fields to change in a knowledge entry; ``null`` clears one."""

    model_config = ConfigDict(extra="allow")


class ImportProblem(BaseModel):
    row: int
    message: str


class ImportReport(BaseModel):
    added: int
    replaced: int
    errors: list[ImportProblem]


class KnowledgeSettings(BaseModel):
    sections: list[Section]
    similarity: float | None
    available: bool


def entry_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Return the fields of an input as geomind sees them, without the app's own."""
    return {key: value for key, value in entry.items() if key != "project"}
