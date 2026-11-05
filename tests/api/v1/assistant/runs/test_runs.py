import json
from uuid import uuid4

from src.api.v1.assistant.runs.services import stored_events
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.redis.models.run_delta import PendingDelta
from src.core.clients.redis.repositories.run_delta import RunDeltaRepository
from tests.api.v1.assistant.conftest import run_url
from tests.api.v1.assistant.recorded import play
from tests.conftest import bearer

REQUEST = {"request": "request-14", "kind": "approval", "message": "Allow?"}
STEP_LIMIT = {
    "request": "request-9",
    "kind": "question",
    "message": "designer: the run took its 30 steps; continue or stop?",
    "options": [
        {"value": "continue", "label": "continue"},
        {"value": "stop", "label": "stop"},
    ],
}
QUESTION = {
    "request": "request-3",
    "kind": "question",
    "message": "Which?",
    "options": [{"value": "a", "label": "A"}],
}


async def store_events(session, run, events) -> None:
    repository = RunEventRepository(session)
    for event in events:
        await repository.add(
            run.id, event.sequence, event.type, event.is_public, event.to_dict()
        )


async def test_runs_list_filters_active(
    client, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    await make_run(chat, owner, "done")
    waiting = await make_run(chat, owner, "waiting")

    everything = await client.get(
        f"/api/v1/assistant/runs?project={project.id}", headers=bearer(owner)
    )
    active = await client.get(
        f"/api/v1/assistant/runs?project={project.id}&status=active",
        headers=bearer(owner),
    )

    assert len(everything.json()["items"]) == 2
    assert [item["id"] for item in active.json()["items"]] == [str(waiting.id)]


async def test_other_member_sees_run_not_found(
    client, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    run = await make_run(await make_chat(await make_project(owner), owner), owner)

    response = await client.get(run_url(run.id), headers=bearer(other))
    missing = await client.get(run_url(uuid4()), headers=bearer(other))

    assert response.status_code == missing.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"


async def test_answer_resumes_a_waiting_run(
    client, make_user, make_project, make_chat, make_run, queue
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    run = await make_run(chat, owner, "waiting", {"request": REQUEST})
    body = {"request": "request-14", "answer": {"approved": False, "reason": "no"}}

    first = await client.post(
        run_url(run.id, "/answer"), json=body, headers=bearer(owner)
    )
    again = await client.post(
        run_url(run.id, "/answer"), json=body, headers=bearer(owner)
    )

    assert first.json()["status"] == "running"
    assert first.json()["request"] is None
    assert queue.sent == [
        ("assistant.runs.resume", str(run.id), "request-14", body["answer"])
    ]
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "run_not_waiting"


async def test_answer_must_fit_the_request(
    client, make_user, make_project, make_chat, make_run, queue
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    approval = await make_run(chat, owner, "waiting", {"request": REQUEST})
    headers = bearer(owner)

    wrong_id = await client.post(
        run_url(approval.id, "/answer"),
        json={"request": "other", "answer": {"approved": True}},
        headers=headers,
    )
    wrong_kind = await client.post(
        run_url(approval.id, "/answer"),
        json={"request": "request-14", "answer": {"text": "yes"}},
        headers=headers,
    )

    assert wrong_id.status_code == wrong_kind.status_code == 422
    assert "request" in wrong_id.json()["error"]["details"]["fields"]
    assert "answer" in wrong_kind.json()["error"]["details"]["fields"]
    assert queue.sent == []


async def test_a_question_with_options_takes_typed_words_too(
    client, make_user, make_project, make_chat, make_run, queue
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    run = await make_run(chat, owner, "waiting", {"request": QUESTION})

    typed = await client.post(
        run_url(run.id, "/answer"),
        json={"request": "request-3", "answer": {"text": "use 45 C instead"}},
        headers=bearer(owner),
    )

    assert typed.status_code == 200, typed.text
    assert queue.sent[0][-1] == {"text": "use 45 C instead"}


async def test_the_step_limit_question_takes_only_its_options(
    client, make_user, make_project, make_chat, make_run, queue
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    run = await make_run(chat, owner, "waiting", {"request": STEP_LIMIT})

    bad = await client.post(
        run_url(run.id, "/answer"),
        json={"request": "request-9", "answer": {"text": "keep going a bit"}},
        headers=bearer(owner),
    )
    good = await client.post(
        run_url(run.id, "/answer"),
        json={"request": "request-9", "answer": {"text": "continue"}},
        headers=bearer(owner),
    )

    assert bad.status_code == 422
    assert good.status_code == 200


async def test_answer_puts_the_run_back_when_the_queue_is_down(
    client, make_user, make_project, make_chat, make_run, queue
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    run = await make_run(chat, owner, "waiting", {"request": REQUEST})
    queue.down = True

    response = await client.post(
        run_url(run.id, "/answer"),
        json={"request": "request-14", "answer": {"approved": True}},
        headers=bearer(owner),
    )
    after = await client.get(run_url(run.id), headers=bearer(owner))

    assert response.status_code == 503
    assert after.json()["status"] == "waiting"
    assert after.json()["request"] == REQUEST


async def test_cancel_sets_the_flag_and_wakes_a_waiting_run(
    client, make_user, make_project, make_chat, make_run, queue, redis
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    running = await make_run(chat, owner, "running")
    waiting = await make_run(chat, owner, "waiting", {"request": REQUEST})
    done = await make_run(chat, owner, "done")
    headers = bearer(owner)

    await client.post(run_url(running.id, "/cancel"), headers=headers)
    await client.post(run_url(waiting.id, "/cancel"), headers=headers)
    refused = await client.post(run_url(done.id, "/cancel"), headers=headers)

    assert await redis.exists(f"job:{running.id}:cancel")
    assert await redis.exists(f"job:{waiting.id}:cancel")
    stand_in = {"approved": False, "reason": "cancelled"}
    assert queue.sent == [
        ("assistant.runs.resume", str(waiting.id), "request-14", stand_in)
    ]
    assert refused.status_code == 409


async def test_log_and_exports(
    client, make_user, make_project, make_chat, make_run, session
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await store_events(session, run, await play(run.id))
    headers = bearer(owner)

    log = await client.get(run_url(run.id, "/log"), headers=headers)
    exported = await client.get(
        run_url(run.id, "/log/export?format=json"), headers=headers
    )
    markdown = await client.get(
        run_url(run.id, "/log/export?format=md"), headers=headers
    )

    assert log.json()["run"]["status"] == "done"
    assert json.loads(exported.text) == log.json()
    assert "attachment" in exported.headers["content-disposition"]
    assert markdown.text.startswith(f"# Run {run.id.hex}")
    assert "save_profile" in markdown.text


async def test_log_of_a_run_without_events_is_a_conflict(
    client, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)

    response = await client.get(run_url(run.id, "/log"), headers=bearer(owner))

    assert response.status_code == 409


def sse_ids(text: str) -> list[str]:
    return [line[4:] for line in text.splitlines() if line.startswith("id: ")]


async def test_events_replay_and_end_at_the_root_run_finished(
    client, make_user, make_project, make_chat, make_run, session
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    events = await play(run.id)
    await store_events(session, run, events)
    headers = bearer(owner)

    full = await client.get(run_url(run.id, "/events"), headers=headers)
    later = await client.get(
        run_url(run.id, "/events"), headers={**headers, "Last-Event-ID": "20"}
    )

    # A person's decision replays as `answer`, with the sequence of geomind's internal
    # `permission` event behind it (contract 1.1.59, QA-058).
    public = [
        event
        for event in events
        if (event.is_public and event.type != "text.delta")
        or (event.type == "permission" and event.rule == "user")
    ]
    assert full.headers["content-type"].startswith("text/event-stream")
    assert sse_ids(full.text) == [str(event.sequence) for event in public]
    assert "event: answer" in full.text
    assert "event: run.finished" in full.text
    assert sse_ids(later.text) == [str(e.sequence) for e in public if e.sequence > 20]


async def test_replay_adds_the_buffered_text_of_a_running_step(
    session_factory, make_user, make_project, make_chat, make_run, redis
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    delta = PendingDelta("analyst", None, 9, "partial", "s1", "Analyst II")
    deltas = RunDeltaRepository(redis)
    await deltas.append(str(run.id), delta, 60)

    events = await stored_events(session_factory, deltas, run.id, -1)

    assert [(e.type, e.sequence, e.data["text"]) for e in events] == [
        ("text.delta", None, "partial")
    ]
    assert events[0].data["buffered"] is True
    assert events[0].data["session"] == "s1"
    assert events[0].data["instance"] == "Analyst II"


async def test_buffered_text_is_one_event_per_step_after_the_stored_events(
    session_factory, session, make_user, make_project, make_chat, make_run, redis
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await store_events(session, run, await play(run.id))
    deltas = RunDeltaRepository(redis)
    await deltas.append(
        str(run.id), PendingDelta("analyst", None, 9, "par", "s1", None), 60
    )
    await deltas.append(
        str(run.id), PendingDelta("analyst", None, 9, "tial", "s1", None), 60
    )

    events = await stored_events(session_factory, deltas, run.id, -1)

    buffered = [e for e in events if e.type == "text.delta"]
    assert len(buffered) == 1
    assert buffered[0] is events[-1]
    assert buffered[0].sequence is None
    assert buffered[0].data["text"] == "partial"
    assert all(e.sequence is not None for e in events[:-1])
    assert not any(e.data.get("buffered") for e in events[:-1])


async def test_replay_gives_a_failed_tool_its_problem_and_no_internal_event(
    client,
    session,
    session_factory,
    redis,
    make_user,
    make_project,
    make_chat,
    make_run,
) -> None:
    user = await make_user()
    run = await make_run(await make_chat(await make_project(user), user), user)
    events = await play(run.id)
    recorded = next(e for e in events if e.type == "tool.result" and e.call_id)
    missing = {
        "code": "case_incomplete",
        "path": "demand",
        "message": "The case is not complete",
        "suggestions": ["demand", "time.start"],
    }
    changed = recorded.model_copy(
        update={"output": {"error": missing}, "is_error": True}
    )
    await store_events(session, run, [changed if e is recorded else e for e in events])
    deltas = RunDeltaRepository(redis)

    stored = await stored_events(session_factory, deltas, run.id, -1)

    finished = [e for e in stored if e.type == "tool.finished"]
    assert finished[0].data["problem"] == missing
    assert all(e.type != "tool.result" for e in stored)


async def test_a_step_says_the_context_window_its_calls_may_hold(
    client,
    session,
    session_factory,
    redis,
    make_user,
    make_project,
    make_chat,
    make_run,
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEOMIND_CONTEXT_WINDOW", "128000")
    user = await make_user()
    run = await make_run(await make_chat(await make_project(user), user), user)
    await store_events(session, run, await play(run.id))

    stored = await stored_events(session_factory, RunDeltaRepository(redis), run.id, -1)

    steps = [e for e in stored if e.type == "step.started"]
    assert steps and all(e.data["context_window"] == 128000 for e in steps)
    others = [e for e in stored if e.type != "step.started"]
    assert all("context_window" not in e.data for e in others)


def stored_request(root: str, sequence: int, request_id: str) -> dict:
    return {
        "type": "request",
        "run_id": root,
        "sequence": sequence,
        "time": "2026-11-05T19:40:00+00:00",
        "agent": "case_lead",
        "parent": root,
        "request": {"kind": "question", "message": "Economics?", "id": request_id},
        "point": "tool",
    }


async def test_a_pending_request_numbered_in_the_past_is_asked_last(
    client, make_user, make_project, make_chat, make_run, session, session_factory
) -> None:
    import fakeredis

    """QA-336: request-797 stored under 797 after event 943; the run's reader asks it last."""
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner, "waiting")
    root = run.id.hex
    events = RunEventRepository(session)
    await events.add(run.id, 943, "step.started", True, {
        "type": "step.started", "run_id": root, "sequence": 943, "index": 6,
        "agent": "case_lead", "parent": root,
    })
    await events.add(run.id, 797, "request", True, stored_request(root, 797, "request-797"))

    first = await client.get(run_url(run.id), headers=bearer(owner))
    again = await client.get(run_url(run.id), headers=bearer(owner))

    assert first.json()["request"]["request"] == "request-797"
    assert again.status_code == 200
    asked = await events.of_type(run.id, "request")
    assert [row.sequence for row in asked] == [944, 797]
    replay = await stored_events(session_factory, RunDeltaRepository(fakeredis.aioredis.FakeRedis()), run.id, -1)
    assert [(item.type, item.sequence) for item in replay][-1] == ("request", 944)
