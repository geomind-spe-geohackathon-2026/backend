"""geomind 0.4.24's per-session figures, built with its own event classes."""

import geomind as gd
import pytest

from src.api.v1.assistant.runs.adapters.callbacks import ToolProblems
from src.api.v1.assistant.runs.services import spending_of, stored_events
from src.core.clients.redis.repositories.run_delta import RunDeltaRepository
from src.core.geomind import windows
from tests.api.v1.assistant.conftest import run_url
from tests.api.v1.assistant.recorded import play
from tests.api.v1.assistant.runs.test_runs import store_events
from tests.conftest import bearer

EVENTS = gd.types.events
RESULTS = gd.types.results
WINDOW = 163840
MODEL = "m/x"


def spent(input_tokens: int, cached: int, cost: float) -> gd.types.Usage:
    return gd.types.Usage(
        input_tokens=input_tokens,
        output_tokens=10,
        cached_tokens=cached,
        cost=cost,
    )


class Log:
    """The events of a root run with one nested session, numbered in order."""

    def __init__(self, root: str) -> None:
        self.root = root
        self.child = f"{root}-c"
        self.events: list = []

    def add(self, kind, run_id: str, agent: str, parent=None, **fields) -> None:
        sequence = len(self.events) + 1
        self.events.append(
            kind(run_id=run_id, agent=agent, parent=parent, sequence=sequence, **fields)
        )

    def step(self, run_id, agent, index, used, cached, parent=None) -> None:
        self.add(
            EVENTS.StepStarted,
            run_id,
            agent,
            parent,
            index=index,
            model=MODEL,
            session=run_id,
            context_window=WINDOW,
        )
        context = RESULTS.CallContext(used=used, window=WINDOW, remaining=WINDOW - used)
        self.add(
            EVENTS.StepFinished,
            run_id,
            agent,
            parent,
            index=index,
            usage=spent(used, cached, 0.001),
            text="",
            context=context,
        )

    def sessions(self) -> list:
        lead = RESULTS.SessionUsage(
            session=self.root,
            agent="lead",
            model=MODEL,
            steps=1,
            tool_calls=1,
            usage=spent(900, 100, 0.001),
            context=RESULTS.SessionContext(peak_used=900, last_used=900, window=WINDOW),
        )
        case = RESULTS.SessionUsage(
            session=self.child,
            agent="lead/case",
            parent=self.root,
            model=MODEL,
            steps=2,
            tool_calls=3,
            usage=spent(11000, 6000, 0.002),
            context=RESULTS.SessionContext(
                peak_used=7000, last_used=7000, window=WINDOW
            ),
        )
        return [lead, case]

    def finish(self) -> None:
        sessions = self.sessions()
        agents = [
            RESULTS.AgentUsage(
                agent=item.agent,
                sessions=1,
                steps=item.steps,
                tool_calls=item.tool_calls,
                usage=item.usage,
            )
            for item in sessions
        ]
        total = RESULTS.TotalUsage(
            input_tokens=11900,
            output_tokens=20,
            cached_tokens=6100,
            cost=0.003,
            steps=3,
            tool_calls=4,
        )
        self.add(
            EVENTS.RunFinished,
            self.child,
            "lead/case",
            self.root,
            status="done",
            stop_reason="answer",
        )
        self.add(
            EVENTS.RunFinished,
            self.root,
            "lead",
            status="done",
            stop_reason="answer",
            sessions=sessions,
            agents=agents,
            total=total,
        )


def run_log(root: str, finished: bool = True) -> Log:
    log = Log(root)
    log.step(root, "lead", 1, 900, 100)
    log.step(log.child, "lead/case", 1, 4000, 2000, root)
    log.step(log.child, "lead/case", 2, 7000, 4000, root)
    if finished:
        log.finish()
    return log


def test_the_public_events_keep_geomind_new_fields() -> None:
    log = run_log("r1")
    problems = ToolProblems()
    data = {event.type: problems.public(event) for event in log.events}

    assert data["step.started"]["session"] == "r1-c"
    assert data["step.started"]["context_window"] == WINDOW
    assert data["step.finished"]["usage"]["cached_tokens"] == 4000
    assert data["step.finished"]["context"] == {
        "used": 7000,
        "window": WINDOW,
        "remaining": WINDOW - 7000,
    }
    root = problems.public(log.events[-1])
    assert root["total"]["cached_tokens"] == 6100
    assert [item["session"] for item in root["sessions"]] == ["r1", "r1-c"]
    assert root["agents"][1]["agent"] == "lead/case"


async def test_replay_passes_the_new_fields_through(
    session, session_factory, redis, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    log = run_log(run.id.hex)
    await store_events(session, run, log.events)

    stored = await stored_events(session_factory, RunDeltaRepository(redis), run.id, -1)

    assert [event.data for event in stored] == [
        ToolProblems().public(event) for event in log.events
    ]
    finished = [event for event in stored if event.type == "step.finished"]
    assert all("context" in event.data for event in finished)
    assert stored[-1].data["total"]["tool_calls"] == 4


async def test_the_agents_route_reads_geomind_0_4_24_events(
    client, session, make_user, make_project, make_chat, make_run, monkeypatch
) -> None:
    monkeypatch.setattr(windows, "fetch_windows", lambda: {})
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    live = run_log(run.id.hex, finished=False)
    await store_events(session, run, live.events)

    body = (await client.get(run_url(run.id, "/agents"), headers=bearer(owner))).json()

    lead, case = body["agents"]
    assert case["session"] == f"{run.id.hex}-c"
    assert case["parent_session"] == lead["session"] == run.id.hex
    assert case["context_window"] == WINDOW
    assert case["context_used"] == 7000 and case["context_left"] == WINDOW - 7000


async def test_the_agents_route_takes_the_finished_figures(
    client, session, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await store_events(session, run, run_log(run.id.hex).events)

    body = (await client.get(run_url(run.id, "/agents"), headers=bearer(owner))).json()

    lead, case = body["agents"]
    assert case["input_tokens"] == 11000 and case["cached_tokens"] == 6000
    assert case["status"] == "finished" and case["steps"] == 2
    assert body["run"]["input_tokens"] == 11900
    assert body["run"]["cached_tokens"] == 6100
    assert body["run"]["tool_calls"] == 4


async def test_a_run_returns_geomind_sessions_agents_and_total(
    client, session, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await store_events(session, run, run_log(run.id.hex).events)

    body = (await client.get(run_url(run.id), headers=bearer(owner))).json()

    assert [item["session"] for item in body["sessions"]] == [
        run.id.hex,
        f"{run.id.hex}-c",
    ]
    case = body["sessions"][1]
    assert case["parent"] == run.id.hex
    assert case["usage"] == {
        "input_tokens": 11000,
        "output_tokens": 10,
        "cached_tokens": 6000,
        "cost": pytest.approx(0.002),
    }
    assert case["context"] == {"peak_used": 7000, "last_used": 7000, "window": WINDOW}
    assert [item["agent"] for item in body["agents"]] == ["lead", "lead/case"]
    assert body["total"] == {
        "input_tokens": 11900,
        "output_tokens": 20,
        "cached_tokens": 6100,
        "cost": pytest.approx(0.003),
        "steps": 3,
        "tool_calls": 4,
    }


async def test_a_recorded_run_total_matches_its_usage(
    client, session, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    events = await play(run.id)
    await store_events(session, run, events)

    body = (await client.get(run_url(run.id), headers=bearer(owner))).json()

    usage = [event for event in events if event.type == "usage"][-1]
    assert body["total"]["input_tokens"] == usage.input_tokens
    assert body["total"]["cost"] == pytest.approx(usage.cost)
    assert {item["agent"] for item in body["sessions"]} == {
        "coordinator",
        "analysis_lead",
    }


async def test_a_run_without_figures_has_null_spending(
    client, session, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    live = await make_run(chat, owner, "running")
    old = await make_run(chat, owner, "done")
    await store_events(session, live, run_log(live.id.hex, finished=False).events)
    older = gd.event_from_dict(
        {
            "type": "run.finished",
            "run_id": old.id.hex,
            "sequence": 1,
            "parent": None,
            "status": "done",
            "stop_reason": "answer",
        }
    )
    await store_events(session, old, [older])
    headers = bearer(owner)

    for run in (live, old):
        body = (await client.get(run_url(run.id), headers=headers)).json()
        assert (body["sessions"], body["agents"], body["total"]) == (None, None, None)
        assert body["usage"] == {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}


async def test_the_runs_list_leaves_the_spending_null(
    client, session, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    run = await make_run(await make_chat(project, owner), owner, "done")
    await store_events(session, run, run_log(run.id.hex).events)

    response = await client.get(
        f"/api/v1/assistant/runs?project={project.id}", headers=bearer(owner)
    )

    (item,) = response.json()["items"]
    assert (item["sessions"], item["agents"], item["total"]) == (None, None, None)


def test_figures_of_the_wrong_shape_are_left_out() -> None:
    spending = spending_of({"sessions": [{"agent": 3}], "total": {"cost": 0.1}})

    assert spending.sessions is None and spending.total is None
    assert spending_of({}).model_dump() == {
        "sessions": None,
        "agents": None,
        "total": None,
    }
