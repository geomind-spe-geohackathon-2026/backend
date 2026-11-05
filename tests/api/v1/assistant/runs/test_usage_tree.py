"""The run row's live totals count nested runs at any depth (QA-144)."""

from types import SimpleNamespace
from uuid import uuid4

from src.api.v1.assistant.runs.adapters.callbacks import UsageTree


def usage(run, parent, tokens, cost=0.0):
    return SimpleNamespace(
        run_id=run, parent=parent, input_tokens=tokens, output_tokens=0, cost=cost
    )


def test_grandchildren_count_before_the_root_has_sent_usage():
    root = uuid4()
    lead, one, two = uuid4(), uuid4(), uuid4()
    tree = UsageTree(root)
    assert tree.add(usage(lead, root, 5)) == {
        "input_tokens": 5,
        "output_tokens": 0,
        "cost": 0.0,
    }
    tree.add(usage(one, lead, 100, 0.1))
    totals = tree.add(usage(two, lead, 50, 0.05))
    assert totals["input_tokens"] == 150
    assert round(totals["cost"], 2) == 0.15


def test_an_ended_child_is_not_counted_twice():
    root, lead, one = uuid4(), uuid4(), uuid4()
    tree = UsageTree(root)
    tree.add(usage(one, lead, 100))
    tree.add(usage(lead, root, 120))
    assert tree.add(usage(one, lead, 100))["input_tokens"] == 120


def test_the_root_usage_never_takes_the_total_down():
    """QA-231: the root's own usage counts only ended children, below the tree's sum."""
    root, lead = uuid4(), uuid4()
    tree = UsageTree(root)
    assert tree.add(usage(lead, root, 2_000))["input_tokens"] == 2_000
    assert tree.add(usage(root, None, 600))["input_tokens"] == 2_000
    assert tree.add(usage(lead, root, 2_500))["input_tokens"] == 2_500


def test_a_resumed_tree_never_goes_below_what_it_gave():
    root, lead = uuid4(), uuid4()
    tree = UsageTree(root)
    tree.add(usage(lead, root, 900))
    assert tree.add(usage(lead, root, 100))["input_tokens"] == 900


def test_the_row_usage_never_goes_down():
    from src.api.v1.assistant.runs.adapters.callbacks import never_lower

    row = SimpleNamespace(input_tokens=5_000, output_tokens=10, cost=0.2)
    kept = never_lower(row, {"input_tokens": 600, "output_tokens": 20, "cost": 0.1, "loop": 1})
    assert kept == {"input_tokens": 5_000, "output_tokens": 20, "cost": 0.2, "loop": 1}


def test_stored_totals_sum_every_session():
    from src.api.v1.assistant.runs.adapters.sessions import stored_totals

    def call(run, tokens, cost):
        return {
            "type": "llm.completed",
            "run_id": run,
            "index": 0,
            "completion": {"usage": {"input_tokens": tokens, "output_tokens": 1, "cost": cost}},
        }

    totals = stored_totals([call("a", 100, 0.1), call("b", 50, 0.05), call("a", 10, 0.0)])
    assert totals["input_tokens"] == 160
    assert totals["output_tokens"] == 3
    assert round(totals["cost"], 2) == 0.15


def test_agent_live_usage_has_steps_and_start():
    """QA-291: a nested session's live line carries its own steps, tokens, cost and start."""
    from src.api.v1.assistant.runs.adapters.callbacks import AgentLive

    live = AgentLive()
    root, lead = uuid4(), uuid4()
    live.note(SimpleNamespace(type="run.started", run_id=lead, time="2026-11-05T19:00:00+01:00"))
    for index in (0, 1, 1):
        live.note(SimpleNamespace(type="step.started", run_id=lead, index=index))
    event = SimpleNamespace(
        run_id=lead, parent=str(root), agent="Geoscientist", instance="Geoscientist II",
        input_tokens=1_000, output_tokens=50, cost=0.01,
    )
    data = live.usage(event)
    assert data["steps"] == 2
    assert data["started"] == "2026-11-05T19:00:00+01:00"
    assert data["instance"] == "Geoscientist II"
    assert (data["input_tokens"], data["output_tokens"], data["cost"]) == (1_000, 50, 0.01)
