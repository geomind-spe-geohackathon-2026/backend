from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class ParameterHistory(BaseModel):
    valid_from: str | None
    params: dict[str, Any]


class Parameters(BaseModel):
    module: str
    type: str
    json_schema: dict[str, Any] = Field(alias="schema")
    values: dict[str, Any]
    missing: list[str]
    ranges: list[str]
    history: list[ParameterHistory]


class ParametersUpdate(BaseModel):
    project: UUID
    base: int | None
    module: str = Field(min_length=1)
    params: dict[str, Any]
    valid_from: AwareDatetime | None = None
    note: str


class ParametersFill(BaseModel):
    project: UUID
    base: int | None
    module: str = Field(min_length=1)
    entry: str
    valid_from: AwareDatetime | None = None
    note: str
