from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from src.core.problems import Problem


class Palette(BaseModel):
    type: str
    title: str
    category: str
    summary: str


class PortKind(BaseModel):
    port: str
    kind: str | None


class ModulePorts(BaseModel):
    type: str
    inlets: list[PortKind]
    outlets: list[PortKind]


class Template(BaseModel):
    name: str
    title: str
    description: str
    purpose: str | None
    modules: int
    categories: list[str]


class FlowsheetModule(BaseModel):
    id: str
    type: str
    title: str
    category: str


class FlowsheetConnection(BaseModel):
    source: str
    target: str
    stream: str | None
    kind: str | None


class Flowsheet(BaseModel):
    project: UUID
    version: int
    spec: dict[str, Any]
    structure: dict[str, Any]
    layout: dict[str, Any]
    modules: list[FlowsheetModule]
    connections: list[FlowsheetConnection]


class FlowsheetCreate(BaseModel):
    project: UUID
    base: int | None
    note: str
    spec: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None
    template: str | None = None
    parameters: dict[str, dict[str, Any]] | None = None

    @model_validator(mode="after")
    def spec_or_template(self) -> Self:
        if (self.spec is None) == (self.template is None):
            raise ValueError("Give either spec or template")
        if self.parameters is not None and self.template is None:
            raise ValueError("parameters go with a template")
        return self


class LayoutUpdate(BaseModel):
    project: UUID
    base: int | None
    layout: dict[str, Any]


class SpecCheck(BaseModel):
    spec: dict[str, Any]
    project: UUID | None = None


class SpecProblems(BaseModel):
    problems: list[Problem]
