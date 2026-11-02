from typing import Literal

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    assistant: Literal["model", "scripted"]
