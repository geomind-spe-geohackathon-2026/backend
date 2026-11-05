from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.core.assistant.schemas import RunStatus


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


class AgentToolCall(BaseModel):
    """One tool call of an agent session: its name, outcome and time, no contents."""

    call_id: str
    tool: str
    error: bool
    duration: float


class AgentSession(BaseModel):
    """One agent session of a run, with its context against its own model's window.

    ``context_used`` is the session's current context: geomind's last reported
    ``used``, else the input of its latest LLM call. ``context_peak`` is the largest
    it has been. ``context_left`` is geomind's ``remaining``, else the window minus
    the context used, never below zero; ``None`` when either is unknown.
    ``cached_tokens`` is part of ``input_tokens``, ``None`` when no call reported it.
    """

    session: str
    parent_session: str | None
    agent: str
    model: str | None
    status: Literal["running", "finished", "failed"] | None
    steps: int
    llm_calls: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int | None
    cost: float
    context_used: int | None
    context_peak: int | None
    context_window: int | None
    context_left: int | None
    tool_calls: list[AgentToolCall]


class AgentRunTotals(BaseModel):
    """A run's figures: geomind's ``total`` when the log has it, else the sum over
    its agent sessions, each LLM call once."""

    id: UUID
    status: RunStatus
    input_tokens: int
    output_tokens: int
    cached_tokens: int | None
    cost: float
    steps: int
    llm_calls: int
    tool_calls: int


class RunAgents(BaseModel):
    """The agent sessions of a run so far, in the order they started."""

    run: AgentRunTotals
    agents: list[AgentSession]


class RunCall(BaseModel):
    """One tool call of a run with its full stored output (the stream keeps a summary)."""

    call_id: str
    tool: str | None
    agent: str | None
    status: Literal["ok", "error"]
    source: str | None
    input: Any
    output: Any
