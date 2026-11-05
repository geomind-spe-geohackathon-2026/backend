from types import SimpleNamespace
from uuid import uuid4

import geomind as gd
import pytest

from src.api.v1.assistant.runs.adapters.callbacks import ToolProblems
from src.api.v1.assistant.runs.adapters.replay import to_runlog
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.geomind import windows
from tests.api.v1.assistant.conftest import run_url
from tests.api.v1.assistant.recorded import play
from tests.api.v1.assistant.runs.test_runs import store_events
from tests.conftest import bearer

EVENTS = gd.types.events
SECRET = "do-not-leak"


def use_windows(monkeypatch: pytest.MonkeyPatch, found: dict[str, int]) -> None:
    monkeypatch.setattr(windows, "fetch_windows", lambda: found)


def usage(input_tokens: int, output_tokens: int, cost: float) -> gd.types.Usage:
    return gd.types.Usage(
        input_tokens=input_tokens, output_tokens=output_tokens, cost=cost
    )


class Script:
    """Build the events of a run with nested sessions, in order."""

    def __init__(self, root: str) -> None:
        self.root = root
        self.events: list = []

    def add(self, kind, session: str, agent: str, parent=None, **fields) -> None:
        self.events.append(
            kind(
                run_id=session,
                agent=agent,
                parent=parent,
                sequence=len(self.events) + 1,
                **fields,
            )
        )

    def start(self, session: str, agent: str, parent=None, parent_step=None) -> None:
        self.add(
            EVENTS.RunStarted,
            session,
            agent,
            parent,
            run=session,
            root=self.root,
            agent_class="tests.Agent",
            max_steps=5,
            parent_step=parent_step,
        )

    def call(self, session, agent, index, model, spent, kind=None, **extra) -> None:
        self.add(EVENTS.StepStarted, session, agent, index=index, model=model)
        completion = gd.types.Completion(text=SECRET, usage=spent, model=model)
        message = gd.Message(role="user", content=SECRET)
        self.add(
            kind or EVENTS.LLMCompleted,
            session,
            agent,
            index=index,
            completion=completion,
            messages=(message,),
            duration=0.5,
            **extra,
        )

    def tool(self, session, agent, index, call_id, tool, is_error=False) -> None:
        self.add(
            EVENTS.ToolRecorded,
            session,
            agent,
            index=index,
            call_id=call_id,
            tool=tool,
            input={"secret": SECRET},
            output=SECRET,
            is_error=is_error,
            duration=0.25,
        )

    def finish(self, session, agent, status="done") -> None:
        self.add(
            EVENTS.RunFinished, session, agent, status=status, stop_reason="answer"
        )


def nested_run(root: str) -> Script:
    """A lead that delegates twice to one agent, each time in a fresh session."""
    child, again = f"{root}-a", f"{root}-b"
    script = Script(root)
    script.start(root, "lead")
    script.call(root, "lead", 1, "big/model", usage(900, 50, 0.01))
    script.start(child, "lead/engineer", root, 1)
    script.call(child, "lead/engineer", 1, "small/model", usage(3000, 100, 0.02))
    script.tool(child, "lead/engineer", 1, "c1", "size_pump")
    script.call(child, "lead/engineer", 2, "small/model", usage(9000, 200, 0.03))
    script.finish(child, "lead/engineer")
    script.tool(root, "lead", 1, "d1", "delegate")
    script.start(again, "lead/engineer", root, 2)
    script.call(again, "lead/engineer", 1, "unknown/model", usage(400, 10, 0.001))
    script.tool(again, "lead/engineer", 1, "c2", "size_pump", is_error=True)
    script.call(
        root,
        "lead",
        2,
        "big/model",
        usage(5000, 70, 0.004),
        kind=EVENTS.Compacted,
        turns=2,
    )
    script.call(root, "lead", 3, "big/model", usage(1200, 60, 0.005))
    return script


async def test_each_agent_session_has_its_own_context(
    client, make_user, make_project, make_chat, make_run, session, monkeypatch
) -> None:
    use_windows(monkeypatch, {"big/model": 1_000_000, "small/model": 8_000})
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    script = nested_run(run.id.hex)
    await store_events(session, run, script.events)

    response = await client.get(run_url(run.id, "/agents"), headers=bearer(owner))

    assert response.status_code == 200
    body = response.json()
    lead, first, second = body["agents"]
    assert [item["session"] for item in body["agents"]] == [
        run.id.hex,
        f"{run.id.hex}-a",
        f"{run.id.hex}-b",
    ]
    assert lead["parent_session"] is None
    assert first["parent_session"] == second["parent_session"] == run.id.hex
    assert first["agent"] == second["agent"] == "lead/engineer"
    assert lead["context_used"] == 1200
    assert lead["context_peak"] == 1200
    assert lead["context_window"] == 1_000_000
    assert lead["context_left"] == 998_800
    assert lead["llm_calls"] == 3 and lead["steps"] == 3
    assert lead["status"] == "running"
    assert first["context_used"] == first["context_peak"] == 9000
    assert first["input_tokens"] == 12000
    assert first["cached_tokens"] == 0
    assert first["context_window"] == 8000 and first["context_left"] == 0
    assert first["status"] == "finished"
    assert first["tool_calls"] == [
        {"call_id": "c1", "tool": "size_pump", "error": False, "duration": 0.25}
    ]
    assert second["context_window"] is None and second["context_left"] is None
    assert second["tool_calls"][0]["error"] is True
    assert SECRET not in response.text


async def test_run_totals_count_each_llm_call_once(
    client, make_user, make_project, make_chat, make_run, session
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    script = nested_run(run.id.hex)
    await store_events(session, run, script.events)

    body = (await client.get(run_url(run.id, "/agents"), headers=bearer(owner))).json()
    log_usage = to_runlog([event.to_dict() for event in script.events])["run"]["usage"]

    totals = body["run"]
    assert totals["id"] == str(run.id)
    assert totals["input_tokens"] == log_usage["input_tokens"] == 19500
    assert totals["output_tokens"] == log_usage["output_tokens"]
    assert totals["cost"] == pytest.approx(log_usage["cost"])
    assert totals["llm_calls"] == 6
    assert totals["tool_calls"] == 3
    assert totals["steps"] == 6


async def test_a_recorded_run_matches_its_log(
    client, make_user, make_project, make_chat, make_run, session, monkeypatch
) -> None:
    use_windows(monkeypatch, {"scripted/model": 1000})
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    events = await play(run.id)
    await store_events(session, run, events)
    headers = bearer(owner)

    body = (await client.get(run_url(run.id, "/agents"), headers=headers)).json()
    log = (await client.get(run_url(run.id, "/log"), headers=headers)).json()

    route, root = body["agents"]
    assert route["session"] == f"{run.id.hex}-route"
    assert route["agent"] == "coordinator" and root["agent"] == "analysis_lead"
    assert route["parent_session"] == root["session"] == run.id.hex
    assert root["status"] == "finished" and root["steps"] == 3
    assert root["context_used"] == 120 and root["context_left"] == 880
    assert body["run"]["input_tokens"] == log["run"]["usage"]["input_tokens"]
    assert body["run"]["output_tokens"] == log["run"]["usage"]["output_tokens"]
    assert body["run"]["cost"] == pytest.approx(log["run"]["usage"]["cost"])
    assert body["run"]["llm_calls"] == sum(len(s["llm_calls"]) for s in log["steps"])
    assert body["run"]["tool_calls"] == sum(len(s["tool_calls"]) for s in log["steps"])


async def test_a_window_geomind_lacks_takes_the_backend_setting(
    client, make_user, make_project, make_chat, make_run, session, monkeypatch
) -> None:
    monkeypatch.setenv("GEOMIND_CONTEXT_WINDOW", "5000")
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await store_events(session, run, nested_run(run.id.hex).events)

    body = (await client.get(run_url(run.id, "/agents"), headers=bearer(owner))).json()

    assert {item["context_window"] for item in body["agents"]} == {5000}
    assert body["agents"][0]["context_left"] == 3800


async def test_a_run_without_events_has_no_agents(
    client, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)

    response = await client.get(run_url(run.id, "/agents"), headers=bearer(owner))

    assert response.status_code == 200
    assert response.json()["agents"] == []
    assert response.json()["run"]["llm_calls"] == 0
    assert response.json()["run"]["cached_tokens"] is None


async def test_other_member_sees_run_not_found_for_agents(
    client, make_user, make_project, make_chat, make_run, session
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await store_events(session, run, nested_run(run.id.hex).events)

    response = await client.get(run_url(run.id, "/agents"), headers=bearer(other))
    missing = await client.get(run_url(uuid4(), "/agents"), headers=bearer(other))
    anonymous = await client.get(run_url(run.id, "/agents"))

    assert response.status_code == missing.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"
    assert missing.json()["error"]["code"] == "run_not_found"
    assert anonymous.status_code == 401


async def test_a_step_says_the_window_of_its_own_model(monkeypatch) -> None:
    use_windows(monkeypatch, {"big/model": 1_000_000, "small/model": 8_000})
    monkeypatch.setenv("GEOMIND_CONTEXT_WINDOW", "")
    await windows.load_windows({"big/model", "small/model"})
    problems = ToolProblems()

    def window(model):
        event = EVENTS.StepStarted(run_id="r", agent="a", index=1, model=model)
        return problems.public(event).get("context_window")

    assert window("big/model") == 1_000_000
    assert window("small/model") == 8_000
    assert window("other/model") is None
    assert window(gd.types.RULE_MODEL) is None
    monkeypatch.setenv("GEOMIND_CONTEXT_WINDOW", "64000")
    assert window("other/model") == 64000


def event(kind: str, run_id: str, agent: str, parent=None, **fields) -> dict:
    """Return a stored event as geomind 0.4.24 writes it."""
    return {"type": kind, "run_id": run_id, "agent": agent, "parent": parent, **fields}


def llm(run_id: str, agent: str, index: int, used: int, parent=None) -> dict:
    spent = {"input_tokens": used, "output_tokens": 10, "cost": 0.001}
    spent = {**spent, "cached_tokens": 5}
    completion = {"text": SECRET, "usage": spent, "model": "m/x"}
    return event(
        "llm.completed", run_id, agent, parent, index=index, completion=completion
    )


def step(run_id, agent, index, used, window, parent=None) -> list[dict]:
    context = {"used": used, "window": window, "remaining": window - used}
    spent = {"input_tokens": used, "output_tokens": 10, "cost": 0.001}
    return [
        event(
            "step.started",
            run_id,
            agent,
            parent,
            index=index,
            model="m/x",
            session=run_id,
            context_window=window,
        ),
        llm(run_id, agent, index, used, parent),
        event(
            "step.finished",
            run_id,
            agent,
            parent,
            index=index,
            usage={**spent, "cached_tokens": 5},
            context=context,
        ),
    ]


def new_shape(root: str, finished: bool) -> list[dict]:
    child = f"{root}-c"
    events = [event("run.started", root, "lead", run=root)]
    events += step(root, "lead", 1, 900, 163840)
    events.append(event("run.started", child, "lead/case", root, run=child))
    events += step(child, "lead/case", 1, 4000, 163840, root)
    events += step(child, "lead/case", 2, 7000, 163840, root)
    if not finished:
        return events
    sessions = [
        {
            "session": root,
            "agent": "lead",
            "parent": None,
            "model": "m/x",
            "steps": 1,
            "tool_calls": 0,
            "usage": {
                "input_tokens": 41200,
                "output_tokens": 1900,
                "cached_tokens": 30100,
                "cost": 0.0123,
            },
            "context": {"peak_used": 9800, "last_used": 9700, "window": 163840},
        },
        {
            "session": child,
            "agent": "lead/case",
            "parent": root,
            "model": "m/x",
            "steps": 2,
            "tool_calls": 0,
            "usage": {
                "input_tokens": 120500,
                "output_tokens": 4100,
                "cached_tokens": 98000,
                "cost": 0.0311,
            },
            "context": {"peak_used": 17400, "last_used": 17000, "window": 163840},
        },
    ]
    total = {
        "input_tokens": 161700,
        "output_tokens": 6000,
        "cached_tokens": 128100,
        "cost": 0.0434,
        "steps": 3,
        "tool_calls": 0,
    }
    events.append(event("run.finished", child, "lead/case", root, status="done"))
    events.append(
        event(
            "run.finished",
            root,
            "lead",
            status="completed",
            stop_reason="answer",
            sessions=sessions,
            agents=[],
            total=total,
        )
    )
    return events


async def store_dicts(session, run, events: list[dict]) -> None:
    repository = RunEventRepository(session)
    for sequence, data in enumerate(events, start=1):
        data = {**data, "sequence": sequence}
        await repository.add(run.id, sequence, data["type"], True, data)


async def test_a_live_run_takes_the_context_geomind_reports(
    client, make_user, make_project, make_chat, make_run, session, monkeypatch
) -> None:
    use_windows(monkeypatch, {"m/x": 1000})
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await store_dicts(session, run, new_shape(run.id.hex, finished=False))

    body = (await client.get(run_url(run.id, "/agents"), headers=bearer(owner))).json()

    lead, case = body["agents"]
    assert case["parent_session"] == lead["session"] == run.id.hex
    assert case["context_used"] == 7000 and case["context_peak"] == 7000
    assert case["context_window"] == 163840
    assert case["context_left"] == 163840 - 7000
    assert case["cached_tokens"] == 10 and case["input_tokens"] == 11000
    assert case["status"] == "running"
    assert body["run"]["input_tokens"] == 11900
    assert body["run"]["cached_tokens"] == 15
    assert SECRET not in str(body)


async def test_a_finished_run_takes_geomind_sessions_and_total(
    client, make_user, make_project, make_chat, make_run, session
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await store_dicts(session, run, new_shape(run.id.hex, finished=True))

    body = (await client.get(run_url(run.id, "/agents"), headers=bearer(owner))).json()

    lead, case = body["agents"]
    assert lead["status"] == case["status"] == "finished"
    assert case["input_tokens"] == 120500 and case["cached_tokens"] == 98000
    assert case["context_used"] == 17000 and case["context_peak"] == 17400
    assert case["context_left"] == 163840 - 17000
    assert case["steps"] == 2 and case["llm_calls"] == 2
    totals = body["run"]
    assert totals["input_tokens"] == 161700
    assert totals["cached_tokens"] == 128100
    assert totals["cost"] == pytest.approx(0.0434)
    assert totals["steps"] == 3 and totals["llm_calls"] == 3


async def test_parallel_instances_of_one_role_are_separate_agents(
    client, make_user, make_project, make_chat, make_run, session, monkeypatch
) -> None:
    use_windows(monkeypatch, {"m/x": 1000})
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    root = run.id.hex
    events = [event("run.started", root, "lead", run=root)]
    for number, name in ((1, "Geoscientist I"), (2, "Geoscientist II")):
        child = f"{root}-g{number}"
        events.append(
            event("run.started", child, "geoscientist", root, run=child, instance=name)
        )
        events += step(child, "geoscientist", 1, 1000 * number, 163840, root)
    await store_dicts(session, run, events)

    body = (await client.get(run_url(run.id, "/agents"), headers=bearer(owner))).json()

    lead, first, second = body["agents"]
    assert lead["instance"] is None
    assert [first["instance"], second["instance"]] == [
        "Geoscientist I",
        "Geoscientist II",
    ]
    assert first["agent"] == second["agent"] == "geoscientist"
    assert first["session"] != second["session"]
    assert [first["context_used"], second["context_used"]] == [1000, 2000]


def test_a_step_passes_geomind_window_through(monkeypatch) -> None:
    use_windows(monkeypatch, {"m/x": 1000})
    step_event = SimpleNamespace(
        type="step.started",
        model="m/x",
        data=lambda: {"index": 1, "model": "m/x", "context_window": 163840},
    )

    assert ToolProblems().public(step_event)["context_window"] == 163840
