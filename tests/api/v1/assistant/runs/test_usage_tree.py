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
