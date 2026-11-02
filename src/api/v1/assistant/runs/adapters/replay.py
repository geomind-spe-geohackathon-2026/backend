from typing import Any

import geomind as gd

from src.api.v1.assistant.runs.adapters.errors import LogUnavailableError


def to_public(stored: dict[str, Any]) -> dict[str, Any]:
    """Return the JSON a client sees for a stored event: ``event.data()``."""
    return gd.event_from_dict(dict(stored)).data()


def to_runlog(stored: list[dict[str, Any]]) -> dict[str, Any]:
    """Return ``gd.runlog`` of a run's stored events, nested runs included."""
    events = [gd.event_from_dict(dict(item)) for item in stored]
    try:
        return gd.runlog(events)
    except gd.errors.RunError as error:
        raise LogUnavailableError(str(error)) from error
