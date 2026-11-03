import os

CONTEXT_WINDOW_SETTING = "GEOMIND_CONTEXT_WINDOW"


def context_window() -> int | None:
    """Return the tokens a model call may hold, as geomind is set; ``None`` when unset.

    geomind compacts a run's context at a share of it, so a chat can show how full the
    context is against this number.
    """
    raw = os.environ.get(CONTEXT_WINDOW_SETTING, "").strip()
    try:
        window = int(raw) if raw else None
    except ValueError:
        return None
    return window if window is not None and window > 0 else None
