from typing import Literal

from pydantic import BaseModel

StepState = Literal["empty", "incomplete", "ready", "running", "done"]


class ProgressStep(BaseModel):
    state: StepState
    label: str


class Progress(BaseModel):
    case: ProgressStep
    plant: ProgressStep
    study: ProgressStep
    results: ProgressStep
    report: ProgressStep
    economics: ProgressStep | None = None
