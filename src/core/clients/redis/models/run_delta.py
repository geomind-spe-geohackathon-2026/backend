from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PendingDelta:
    """The text a step has streamed so far, kept until the step finishes.

    ``session`` is the run id of the agent session the step belongs to; parallel
    instances of one role share ``agent`` and ``parent`` but not it (IMP-025).
    ``instance`` is the instance's name, ``None`` outside a team of instances.
    """

    agent: str
    parent: str | None
    index: int
    text: str
    session: str | None
    instance: str | None
