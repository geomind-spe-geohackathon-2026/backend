"""Step events carry ``ts``, the event's own clock, in the stream and the replay."""

from datetime import datetime, timezone
from types import SimpleNamespace

from src.api.v1.assistant.runs.adapters.callbacks import ToolProblems


def step(kind, time):
    return SimpleNamespace(
        type=kind, time=time, model=None, data=lambda: {"index": 1, "agent": "a"}
    )


def test_step_events_get_ts_from_the_event_time():
    stamp = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
    for kind in ("step.started", "step.finished"):
        data = ToolProblems().public(step(kind, stamp))
        assert data["ts"] == stamp.isoformat()


def test_other_events_and_missing_time_get_no_ts():
    assert "ts" not in ToolProblems().public(step("step.finished", None))
    assert "ts" not in ToolProblems().public(step("run.started", datetime.now()))


def test_run_log_steps_get_ts():
    from src.api.v1.assistant.runs.adapters.replay import with_step_ts

    stamp = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
    ev = lambda t, **k: SimpleNamespace(type=t, run_id="r", index=1, time=stamp, call_id="c", **k)
    log = {"steps": [{"index": 1}]}
    out = with_step_ts(log, [ev("step.started"), ev("llm.completed")])
    assert out["steps"][0]["ts"] == stamp.isoformat()


def test_a_user_wait_is_its_own_span_and_on_its_call():
    """QA-220: the card's open time is logged, not hidden in a gap between steps."""
    from datetime import timedelta

    from src.api.v1.assistant.runs.adapters.replay import with_waits

    shown = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
    answered = shown + timedelta(seconds=755)
    request = SimpleNamespace(id="q1", kind="approval", call_id="c1")
    call = SimpleNamespace(id="c1", name="set_case")
    events = [
        SimpleNamespace(type="request", request=request, call=call, agent="a", run_id="r", time=shown),
        SimpleNamespace(type="permission", rule="user", decision="wait", request=request, time=shown),
        SimpleNamespace(type="request", request=request, call=call, agent="a", run_id="r", time=shown + timedelta(seconds=60)),
        SimpleNamespace(type="permission", rule="user", decision="allow", request=request, tool="set_case", time=answered),
    ]
    log = {"steps": [{"tool_calls": [{"call_id": "c1", "duration": 0.0}]}]}
    out = with_waits(log, events)
    assert out["waits"][0]["duration"] == 755
    assert out["waits"][0]["ended"] == answered.isoformat()
    assert out["waits"][0]["tool"] == "set_case"
    assert out["steps"][0]["tool_calls"][0]["wait"] == 755


def test_an_open_card_has_no_end_yet():
    from src.api.v1.assistant.runs.adapters.replay import wait_spans

    request = SimpleNamespace(id="q1", kind="question", call_id=None)
    events = [SimpleNamespace(type="request", request=request, call=None, agent="a", run_id="r", time=datetime.now(timezone.utc))]
    span = wait_spans(events)[0]
    assert span["ended"] is None and span["duration"] is None
