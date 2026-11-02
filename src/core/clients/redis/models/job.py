from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JobProgress:
    done: int
    total: int
