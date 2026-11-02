from typing import Any
from uuid import UUID

from pydantic import BaseModel

from src.core.problems import Missing, Problem


class CaseFile(BaseModel):
    name: str
    size: int


class Case(BaseModel):
    project: UUID
    version: int
    content: dict[str, Any]
    files: list[CaseFile]
    missing: list[Missing]
    problems: list[Problem]


class CaseCreate(BaseModel):
    project: UUID
    base: int | None
    note: str
    content: dict[str, Any]


class CaseCheck(BaseModel):
    content: dict[str, Any]
    project: UUID | None = None


class CaseProblems(BaseModel):
    missing: list[Missing]
    problems: list[Problem]
    plant_missing: list[Missing] = []
    has_plant: bool = False


class Series(BaseModel):
    name: str
    unit: str
    points: list[tuple[str, float]]


class SeriesList(BaseModel):
    series: list[Series]
