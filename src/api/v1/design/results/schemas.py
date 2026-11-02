from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class Kpi(BaseModel):
    name: str
    title: str
    value: float | None
    unit: str
    reason: str | None


class Checks(BaseModel):
    passed: int
    failed: int
    not_assessed: int


class Result(BaseModel):
    id: UUID
    name: str
    study: UUID | None
    case_version: int | None
    plant_version: int | None
    kpis: list[Kpi]
    checks: Checks
    created: datetime


class Capacity(BaseModel):
    name: str
    title: str
    value: float | None
    unit: str
    reason: str | None


class Constraint(BaseModel):
    name: str
    title: str
    status: Literal["pass", "fail", "not_assessed"]
    message: str


class Coverage(BaseModel):
    date: str
    source: Literal["geothermal", "backup", "short"]


class ResultDetail(Result):
    capacities: list[Capacity]
    coverage: list[Coverage] | None
    constraints: list[Constraint]
    series: list[Any]


class ResultComparison(BaseModel):
    items: list[Result]
    pareto: list[UUID]
