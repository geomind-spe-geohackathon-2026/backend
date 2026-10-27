from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimit:
    limit: int
    requests: int
    retry_after: int

    @property
    def remaining(self) -> int:
        return max(self.limit - self.requests, 0)

    @property
    def exceeded(self) -> bool:
        return self.requests > self.limit
