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
