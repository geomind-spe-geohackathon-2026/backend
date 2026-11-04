class AdapterFailedError(Exception):
    """geomind refused to build or run a run; the message is geomind's."""


class LogUnavailableError(Exception):
    """A run has no log that geomind can read yet."""


class StaleRequestError(Exception):
    """An answer named a request that is not the run's pending one (QA-056)."""

    def __init__(self, expected: str) -> None:
        super().__init__(f"the run waits on {expected}")
        self.expected = expected
