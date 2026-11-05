"""The agent sessions of a run, read from its stored events so far.

One agent session is one geomind run: it has its own ``run_id`` and its own
conversation, so its context is counted on its own and never summed over the run.
A delegated agent, the routing call and any fresh session an agent opens each have
their own session. Only names, counts, tokens, cost and timings are read here,
never message contents, tool inputs or tool outputs.

geomind's own figures come first wherever the events carry them: ``session`` and
``context_window`` on ``step.started``, ``context`` on ``step.finished``, and
``sessions`` and ``total`` on the root ``run.finished`` (the keys of geomind
0.4.24's ``StepStarted``, ``StepFinished`` and ``RunFinished``). A log written before
0.4.24 has none of them and is counted here from its LLM calls and tool results, the
way ``runlog`` counts them. The stored dicts are read as they are, so a field the
installed geomind does not know yet is still seen.
"""

from collections.abc import Iterable
from typing import Any

import geomind as gd

from src.core.geomind.windows import load_windows, window_of

RUN_STARTED = "run.started"
RUN_FINISHED = "run.finished"
STEP_STARTED = "step.started"
STEP_FINISHED = "step.finished"
LLM_COMPLETED = "llm.completed"
TOOL_RESULT = "tool.result"
SESSION_STATUS = {
    "done": "finished",
    "completed": "finished",
    "failed": "failed",
    "waiting": "running",
}


def llm_event_types() -> tuple[str, ...]:
    """Return the event types geomind counts as LLM calls in ``runlog``."""
    return tuple(gd.types.events.LLM_EVENTS)


def mapping(value: Any) -> dict[str, Any]:
    """Return a value when it is a mapping, else an empty one."""
    return value if isinstance(value, dict) else {}


def number(value: Any) -> int | None:
    """Return a whole number of tokens, or ``None`` for anything else."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value)


def amount(value: Any) -> float:
    """Return a cost, zero for anything that is not a number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def session_of(event: dict[str, Any]) -> str | None:
    """Return the agent session an event belongs to.

    geomind names it in ``session`` from 0.4.24 on; before, the session is the run
    id that ``runlog`` keys its steps on, which is the same value.
    """
    session = event.get("session")
    return session if isinstance(session, str) and session else event.get("run_id")


def parent_session_of(event: dict[str, Any]) -> str | None:
    """Return the session that opened the session of an event."""
    parent = event.get("parent")
    return None if not parent or parent == session_of(event) else parent


def new_session(event: dict[str, Any]) -> dict[str, Any]:
    """Return the empty tally of a session first seen in ``event``."""
    return {
        "session": session_of(event),
        "parent_session": parent_session_of(event),
        "agent": event.get("agent") or "",
        "instance": event.get("instance"),
        "model": None,
        "status": "running",
        "step_indexes": set(),
        "llm_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": None,
        "cost": 0.0,
        "context_used": None,
        "context_peak": None,
        "reported_window": None,
        "reported_left": None,
        "tool_calls": [],
    }


def add_step(tally: dict[str, Any], event: dict[str, Any]) -> None:
    """Note a step's index when the event has one."""
    index = event.get("index")
    if isinstance(index, int):
        tally["step_indexes"].add(index)


def use_context(tally: dict[str, Any], used: int) -> None:
    """Set a session's current context and its peak so far."""
    tally["context_used"] = used
    tally["context_peak"] = max(tally["context_peak"] or 0, used)


def count_llm_call(tally: dict[str, Any], event: dict[str, Any]) -> None:
    """Add one LLM call; a plain completion's input is the session's current context."""
    completion = mapping(event.get("completion"))
    usage = mapping(completion.get("usage"))
    tally["llm_calls"] += 1
    tally["input_tokens"] += number(usage.get("input_tokens")) or 0
    tally["output_tokens"] += number(usage.get("output_tokens")) or 0
    tally["cost"] += amount(usage.get("cost"))
    cached = number(usage.get("cached_tokens"))
    if cached is not None:
        tally["cached_tokens"] = (tally["cached_tokens"] or 0) + cached
    tally["model"] = completion.get("model") or tally["model"]
    tally["status"] = "running"
    add_step(tally, event)
    used = number(usage.get("input_tokens"))
    if event.get("type") == LLM_COMPLETED and used is not None:
        use_context(tally, used)
        tally["reported_left"] = None


def start_step(tally: dict[str, Any], event: dict[str, Any]) -> None:
    """Note a step's model and the window geomind gives for it."""
    add_step(tally, event)
    tally["model"] = event.get("model") or tally["model"]
    tally["status"] = "running"
    window = number(event.get("context_window"))
    if window is not None:
        tally["reported_window"] = window


def finish_step(tally: dict[str, Any], event: dict[str, Any]) -> None:
    """Take the context geomind reports at the end of a step."""
    context = mapping(event.get("context"))
    used = number(context.get("used"))
    if used is not None:
        use_context(tally, used)
        tally["reported_left"] = number(context.get("remaining"))
    window = number(context.get("window"))
    if window is not None:
        tally["reported_window"] = window


def tool_call(event: dict[str, Any]) -> dict[str, Any]:
    """Return the public figures of one tool result."""
    return {
        "call_id": str(event.get("call_id")),
        "tool": str(event.get("tool") or ""),
        "error": bool(event.get("is_error")),
        "duration": amount(event.get("duration")),
    }


def note(tally: dict[str, Any], event: dict[str, Any]) -> None:
    """Add what one event says about its session."""
    kind = event.get("type")
    if kind in llm_event_types():
        count_llm_call(tally, event)
    elif kind == STEP_STARTED:
        start_step(tally, event)
    elif kind == STEP_FINISHED:
        finish_step(tally, event)
    elif kind == TOOL_RESULT and event.get("call_id") is not None:
        tally["tool_calls"].append(tool_call(event))
    elif kind == RUN_FINISHED:
        tally["status"] = SESSION_STATUS.get(event.get("status"))


def is_root_summary(event: dict[str, Any]) -> bool:
    """Tell a root ``run.finished`` that carries geomind's sessions or total."""
    return (
        event.get("type") == RUN_FINISHED
        and not event.get("parent")
        and (bool(event.get("sessions")) or bool(event.get("total")))
    )


def take_summary(tally: dict[str, Any], item: dict[str, Any]) -> None:
    """Replace a session's figures with the ones geomind summed for it."""
    usage = mapping(item.get("usage"))
    context = mapping(item.get("context"))
    for name in ("input_tokens", "output_tokens"):
        value = number(usage.get(name))
        if value is not None:
            tally[name] = value
    if "cost" in usage:
        tally["cost"] = amount(usage.get("cost"))
    if "cached_tokens" in usage:
        tally["cached_tokens"] = number(usage.get("cached_tokens"))
    tally["agent"] = item.get("agent") or tally["agent"]
    tally["model"] = item.get("model") or tally["model"]
    if "parent" in item:
        tally["parent_session"] = item.get("parent") or None
    last, peak = number(context.get("last_used")), number(context.get("peak_used"))
    if last is not None:
        tally["context_used"], tally["reported_left"] = last, None
    if peak is not None:
        tally["context_peak"] = peak
    window = number(context.get("window"))
    if window is not None:
        tally["reported_window"] = window
    steps = number(item.get("steps"))
    if steps is not None:
        tally["steps"] = steps


def tally_sessions(
    events: Iterable[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    """Return the sessions in start order and the root's latest summary still valid.

    A summary is dropped when an LLM call follows it, as after a waiting run resumed.
    """
    tallies: dict[str, dict[str, Any]] = {}
    summary = None
    for event in events:
        key = session_of(event)
        if not isinstance(key, str):
            continue
        if key not in tallies:
            tallies[key] = new_session(event)
        note(tallies[key], event)
        if tallies[key]["instance"] is None and event.get("instance"):
            tallies[key]["instance"] = event["instance"]
        if is_root_summary(event):
            summary = event
        elif event.get("type") in llm_event_types():
            summary = None
    return tallies, summary


def apply_summary(
    tallies: dict[str, dict[str, Any]], summary: dict[str, Any] | None
) -> None:
    """Take geomind's per-session figures where the root summary has them."""
    for item in (summary or {}).get("sessions") or ():
        item = mapping(item)
        key = item.get("session")
        if not isinstance(key, str):
            continue
        if key not in tallies:
            tallies[key] = new_session({"run_id": key, **item})
            tallies[key]["status"] = None
        take_summary(tallies[key], item)


def finished(tally: dict[str, Any]) -> dict[str, Any]:
    """Return a session's row, with its window and what is left of it."""
    indexes = tally.pop("step_indexes")
    steps = tally.pop("steps", len(indexes))
    reported_window = tally.pop("reported_window")
    reported_left = tally.pop("reported_left")
    window = reported_window
    if window is None:
        window = window_of(tally["model"])
    used = tally["context_used"]
    if window is None or used is None:
        left = None
    else:
        left = max(reported_left if reported_left is not None else window - used, 0)
    return {**tally, "steps": steps, "context_window": window, "context_left": left}


async def agent_sessions(
    stored: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return one row per agent session in start order, and geomind's total if any."""
    tallies, summary = tally_sessions(mapping(item) for item in stored)
    apply_summary(tallies, summary)
    await load_windows(tally["model"] for tally in tallies.values())
    rows = [finished(tally) for tally in tallies.values()]
    total = mapping((summary or {}).get("total")) or None
    return rows, total


def summed_cached(sessions: list[dict[str, Any]]) -> int | None:
    """Return the cached tokens of all sessions, ``None`` when none reported any."""
    known = [item["cached_tokens"] for item in sessions]
    known = [value for value in known if value is not None]
    return sum(known) if known else None


def run_totals(
    sessions: list[dict[str, Any]], total: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return a run's figures: geomind's ``total`` when given, else the session sum.

    Each LLM call is counted once: geomind also adds a nested run's usage to its
    parent's state, so only the calls are summed here, as ``runlog`` sums its
    ``run.usage``.
    """
    summed = {
        "input_tokens": sum(item["input_tokens"] for item in sessions),
        "output_tokens": sum(item["output_tokens"] for item in sessions),
        "cached_tokens": summed_cached(sessions),
        "cost": sum(item["cost"] for item in sessions),
        "steps": sum(item["steps"] for item in sessions),
        "llm_calls": sum(item["llm_calls"] for item in sessions),
        "tool_calls": sum(len(item["tool_calls"]) for item in sessions),
    }
    if not total:
        return summed
    given = {name: number(total.get(name)) for name in summed if name in total}
    if "cost" in total:
        given["cost"] = amount(total.get("cost"))
    known = {key: value for key, value in given.items() if value is not None}
    return {**summed, **known}


def stored_totals(stored: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a run's input and output tokens and cost from its stored events (QA-231).

    The same figures as ``run_totals`` of ``agent_sessions``, without the context windows.
    """
    tallies, summary = tally_sessions(mapping(item) for item in stored)
    apply_summary(tallies, summary)
    sessions = list(tallies.values())
    summed = {
        "input_tokens": sum(item["input_tokens"] for item in sessions),
        "output_tokens": sum(item["output_tokens"] for item in sessions),
        "cost": sum(item["cost"] for item in sessions),
    }
    total = mapping((summary or {}).get("total"))
    for name in ("input_tokens", "output_tokens"):
        value = number(total.get(name))
        if value is not None:
            summed[name] = value
    if "cost" in total:
        summed["cost"] = amount(total.get("cost"))
    return summed
