from typing import Any

import geomind as gd

from src.api.v1.assistant.runs.adapters.errors import LogUnavailableError


def rebuilt(stored: dict[str, Any]) -> Any | None:
    """Return a stored event as geomind's; a type this version lacks gives none."""
    try:
        return gd.event_from_dict(dict(stored))
    except gd.errors.RunError:
        return None


def known_events(stored: list[dict[str, Any]]) -> list[Any]:
    """Return the stored events this geomind version knows, in order."""
    events = [rebuilt(item) for item in stored]
    return [event for event in events if event is not None]


def to_runlog(stored: list[dict[str, Any]]) -> dict[str, Any]:
    """Return ``gd.runlog`` of a run's stored events, nested runs included."""
    try:
        return gd.runlog(known_events(stored))
    except gd.errors.RunError as error:
        raise LogUnavailableError(str(error)) from error
