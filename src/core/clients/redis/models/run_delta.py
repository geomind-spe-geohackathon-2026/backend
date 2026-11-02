from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PendingDelta:
    """The text a step has streamed so far, kept until the step finishes."""

    agent: str
    parent: str | None
    index: int
    text: str
