from typing import Any

import geomind as gd

from src.api.v1.assistant.runs.adapters.errors import LogUnavailableError

LLM_EVENTS = ("llm.completed", "compaction")
"""geomind's calls that make a step of the log."""


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
    events = known_events(stored)
    try:
        log = gd.runlog(events)
    except gd.errors.RunError as error:
        raise LogUnavailableError(str(error)) from error
    return with_step_ts(log, events)


def with_step_ts(log: dict[str, Any], events: list[Any]) -> dict[str, Any]:
    """Add ``ts`` (when the step started) to each step of a run log.

    ``gd.runlog`` lists a step when its first call is seen, keyed by run id and index; the same
    walk over the events gives the step's key, so the steps line up one to one. The clock is
    the stored ``step.started`` time, else the first event of the step.
    """
    keys: list[tuple[Any, Any]] = []
    started: dict[tuple[Any, Any], Any] = {}
    first: dict[tuple[Any, Any], Any] = {}
    for event in events:
        key = (getattr(event, "run_id", None), getattr(event, "index", None))
        stamp = getattr(event, "time", None)
        if event.type == "step.started":
            started[key] = stamp
        if event.type in LLM_EVENTS or (
            event.type == "tool.result" and event.call_id is not None
        ):
            if key not in first:
                keys.append(key)
                first[key] = stamp
    steps = log["steps"]
    if len(keys) != len(steps):
        return log
    for step, key in zip(steps, keys):
        stamp = started.get(key) or first[key]
        step["ts"] = (
            stamp.isoformat() if hasattr(stamp, "isoformat") else stamp
        ) if stamp is not None else None
    return log
