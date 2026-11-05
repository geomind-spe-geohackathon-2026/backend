from typing import Literal

from pydantic import BaseModel

StepState = Literal["empty", "incomplete", "ready", "running", "done"]


class ProgressStep(BaseModel):
    state: StepState
    label: str


class PlantStep(ProgressStep):
    result: str | None = None
    """While no plant version is saved: the newest result's id, whose design 'Use this design
    as the plant' adopts (QA-355); else ``None``."""


class Progress(BaseModel):
    case: ProgressStep
    plant: PlantStep
    study: ProgressStep
    results: ProgressStep
    report: ProgressStep
    economics: ProgressStep | None = None
