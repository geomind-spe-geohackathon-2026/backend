class AdapterFailedError(Exception):
    """geomind refused to build or run a run; the message is geomind's."""


class LogUnavailableError(Exception):
    """A run has no log that geomind can read yet."""
