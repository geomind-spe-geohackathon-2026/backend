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
    feasible: bool
    created: datetime
    role: Literal["design", "sensitivity", "uncertainty"]
    doublets: float | None
    depth: float | None
    depth_unit: str | None


class Capacity(BaseModel):
    name: str
    title: str
    kind: str
    value: float | None
    unit: str
    peak: float | None
    peak_unit: str
    share: float | None
    reason: str | None


class Constraint(BaseModel):
    name: str
    title: str
    module: str | None
    status: Literal["pass", "fail", "not_assessed"]
    message: str
    value: float | None
    unit: str
    limit: str
    margin: float | None
    near: bool
    worst: str | None


class Figure(BaseModel):
    value: float
    unit: str


class CoverageLabels(BaseModel):
    """What ``geothermal`` and ``backup`` are in this plant (gemini 0.6.31, QA-322)."""

    main: str
    other: str | None = None


class CoverageDay(BaseModel):
    date: str
    source: Literal["geothermal", "backup", "short"]
    demand: Figure
    geothermal: Figure
    backup: Figure
    short: Figure
    failed_steps: Figure
    electricity: Figure | None = None
    no_demand: bool = False
    labels: CoverageLabels | None = None


class Coverage(BaseModel):
    heating: list[CoverageDay] = []
    cooling: list[CoverageDay] = []


class TornadoRow(BaseModel):
    parameter: str
    metric: str
    low: str
    high: str
    at_low: float | None
    at_high: float | None
    effect: float | None
    unit: str
    feasible_low: bool | None = None
    feasible_high: bool | None = None


class SpreadRow(BaseModel):
    name: str
    metric: str
    mean: float | None
    p5: float | None
    p50: float | None
    p95: float | None
    unit: str
    draws: int
    feasible: int | None = None


class AdoptedDesign(BaseModel):
    plant_version: int


class ResultDetail(Result):
    capacities: list[Capacity]
    sizes: list[Capacity]
    tornado: list[TornadoRow] | None
    spread: list[SpreadRow] | None
    coverage: Coverage | None
    constraints: list[Constraint]
    series: list[Any]


class DesignSpread(BaseModel):
    result: UUID
    uncertainty: UUID
    metric: str
    p5: float | None
    p95: float | None


class ResultComparison(BaseModel):
    items: list[Result]
    pareto: list[UUID]
    spreads: list[DesignSpread]
