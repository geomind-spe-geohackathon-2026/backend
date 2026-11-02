from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

SVG_LIMIT = 2_000_000

SectionKey = Literal[
    "summary",
    "design",
    "capacities",
    "coverage",
    "checks",
    "costs",
    "findings",
    "agentlog",
    "appendix",
]


class ReportRequest(BaseModel):
    project: UUID
    result: UUID
    run: UUID | None = None
    include: list[SectionKey]


class ReportExport(ReportRequest):
    format: Literal["md", "pdf"]
    flowsheet_svg: str | None = Field(default=None, max_length=SVG_LIMIT)


class ReportSection(BaseModel):
    key: SectionKey
    title: str
    markdown: str


class Report(BaseModel):
    title: str
    sections: list[ReportSection]
    flowsheet: dict[str, list[dict[str, Any]]]


class ReportPart(BaseModel):
    key: SectionKey
    title: str
