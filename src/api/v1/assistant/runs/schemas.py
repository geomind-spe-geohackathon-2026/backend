from typing import Any

from pydantic import BaseModel, ConfigDict


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: str | None = None


class Reply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class RunAnswer(BaseModel):
    """The user's answer to the request a waiting run shows."""

    model_config = ConfigDict(extra="forbid")

    request: str
    answer: Approval | Reply

    def to_dict(self) -> dict[str, Any]:
        """Return the answer in the shape geomind resumes with."""
        return self.answer.model_dump(exclude_none=True)
