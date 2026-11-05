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
    return with_waits(with_step_ts(log, events), events)


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


def stamp_of(value: Any) -> str | None:
    """Return a clock value as ISO text."""
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def wait_spans(events: list[Any]) -> list[dict[str, Any]]:
    """Return one span per request the user settled: from the card shown to the answer (QA-220).

    An approval-gated call and ``ask_user`` end at once with the card, so their duration is 0
    and the user's wait showed only as a gap between steps. A span starts at the first
    ``request`` event of a request id (one asked again after a restart keeps its first time)
    and ends at the user's ``permission`` decision on it; a request not answered yet has no end.
    A parent's ``wait`` decision on a nested run's request is not an answer.
    """
    spans: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.type == "request":
            request = getattr(event, "request", None)
            key = getattr(request, "id", None)
            if key is None or key in spans:
                continue
            spans[key] = {
                "request": key,
                "kind": getattr(request, "kind", None),
                "call_id": getattr(request, "call_id", None)
                or getattr(getattr(event, "call", None), "id", None),
                "tool": getattr(getattr(event, "call", None), "name", None),
                "agent": getattr(event, "agent", None),
                "run_id": getattr(event, "run_id", None),
                "started": getattr(event, "time", None),
                "ended": None,
                "decision": None,
            }
        elif event.type == "permission" and getattr(event, "rule", None) == "user":
            request = getattr(event, "request", None)
            span = spans.get(getattr(request, "id", None))
            if span is None or span["ended"] is not None or event.decision == "wait":
                continue
            span["ended"] = getattr(event, "time", None)
            span["decision"] = event.decision
            span["tool"] = span["tool"] or getattr(event, "tool", None)
    return [finished_span(span) for span in spans.values()]


def finished_span(span: dict[str, Any]) -> dict[str, Any]:
    """Return a wait span with ISO times and its length in seconds."""
    started, ended = span["started"], span["ended"]
    duration = None
    if hasattr(started, "timestamp") and hasattr(ended, "timestamp"):
        duration = round(ended.timestamp() - started.timestamp(), 3)
    return {
        **span,
        "run_id": None if span["run_id"] is None else str(span["run_id"]),
        "started": stamp_of(started),
        "ended": stamp_of(ended),
        "duration": duration,
    }


def with_waits(log: dict[str, Any], events: list[Any]) -> dict[str, Any]:
    """Add the user's waits to a run log: ``waits`` spans and ``wait`` on the gated call.

    A tool call whose card the user answered gets ``wait``, the seconds the card was open,
    next to its own ``duration`` (QA-220).
    """
    spans = wait_spans(events)
    log["waits"] = spans
    waited = {span["call_id"]: span["duration"] for span in spans if span["call_id"]}
    for step in log.get("steps") or ():
        for call in step.get("tool_calls") or ():
            if isinstance(call, dict) and call.get("call_id") in waited:
                call["wait"] = waited[call["call_id"]]
    return log
