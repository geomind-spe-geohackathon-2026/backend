from typing import Literal
from uuid import UUID

from pydantic import BaseModel

SectionKey = Literal["capacities", "design", "checks", "costs", "agentlog"]


class ReportRequest(BaseModel):
    project: UUID
    result: UUID
    run: UUID | None = None
    include: list[SectionKey]


class ReportExport(ReportRequest):
    format: Literal["md", "pdf"]


class ReportSection(BaseModel):
    key: SectionKey
    title: str
    markdown: str


class Report(BaseModel):
    title: str
    sections: list[ReportSection]


class ReportPart(BaseModel):
    key: SectionKey
    title: str
