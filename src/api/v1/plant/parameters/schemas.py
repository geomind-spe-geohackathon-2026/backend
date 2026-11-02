from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class ParameterHistory(BaseModel):
    valid_from: str | None
    params: dict[str, Any]


class RangeEnds(BaseModel):
    min: float | None
    max: float | None


class SearchRange(RangeEnds):
    unit: str | None
    units: dict[str, RangeEnds]


class PlantSearchRange(SearchRange):
    value: Any


class PlantSearch(BaseModel):
    search: dict[str, PlantSearchRange]


class RangeUpdate(BaseModel):
    min: float | None = None
    max: float | None = None
    unit: str | None = None


class PlantRangesUpdate(BaseModel):
    project: UUID
    base: int | None
    ranges: dict[str, RangeUpdate]
    note: str


class Parameters(BaseModel):
    module: str
    type: str
    json_schema: dict[str, Any] = Field(alias="schema")
    values: dict[str, Any]
    missing: list[str]
    ranges: list[str]
    search: dict[str, SearchRange]
    history: list[ParameterHistory]


class ParametersUpdate(BaseModel):
    project: UUID
    base: int | None
    module: str = Field(min_length=1)
    params: dict[str, Any]
    ranges: dict[str, RangeUpdate] = {}
    valid_from: AwareDatetime | None = None
    note: str


class ParametersFill(BaseModel):
    project: UUID
    base: int | None
    module: str = Field(min_length=1)
    entry: str
    valid_from: AwareDatetime | None = None
    note: str
