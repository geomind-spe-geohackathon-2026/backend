import json

import fakeredis
import geomind as gd
import pytest

from src.api.v1.assistant.runs import execution
from src.api.v1.assistant.runs.adapters import session as session_adapter
from src.api.v1.assistant.runs.adapters.fake import says
from src.api.v1.assistant.runs.adapters.session import Resources
from src.api.v1.assistant.runs.services import run_channel
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.redis.repositories.job import JobRepository, SyncJobRepository
from src.core.jobs import control
from src.core.settings import settings
from tests.api.v1.assistant.conftest import run_url, use_models
from tests.conftest import bearer
from tests.routes import route_exists


@pytest.fixture
def server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture
def resources(session_factory, server) -> Resources:
    redis = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    sync = fakeredis.FakeRedis(server=server, decode_responses=True)
    return Resources(session_factory, redis, SyncJobRepository(sync, 60), None)


@pytest.fixture(autouse=True)
def scripted(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ASSISTANT_LLM", "fake")


async def reload(session, run_id):
    run = await RunRepository(session).get_by_id(run_id)
    await session.refresh(run)
    return run


async def test_run_pauses_for_approval_then_finishes(
    client, session, resources, make_user, make_project, make_chat, make_run, queue
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    run = await make_run(await make_chat(project, owner), owner)
    pubsub = resources.redis.pubsub()
    await pubsub.subscribe(run_channel(run.id))
    await pubsub.get_message(timeout=0.2)

    await execution.begin(resources, run.id)
    waiting = await reload(session, run.id)

    assert waiting.error is None
    assert waiting.status == "waiting"
    assert waiting.loop == "tool"
    assert waiting.request["kind"] == "approval"
    assert waiting.started is not None

    headers = bearer(owner)
    body = {"request": waiting.request["request"], "answer": {"approved": True}}
    await client.post(run_url(run.id, "/answer"), json=body, headers=headers)
    _, request_id, answer = queue.sent[0][1:]
    await execution.carry_on(resources, run.id, request_id, answer)
    done = await reload(session, run.id)

    assert done.status == "done"
    assert done.ended is not None
    assert done.input_tokens > 0 and done.cost > 0
    assistant = [
        m
        for m in await MessageRepository(session).history(done.chat_id)
        if m.role == "assistant"
    ]
    assert [m.run_id for m in assistant] == [run.id]
    activity = await ActivityRepository(session).latest(project.id, 5)
    assert activity[0].text == "Assistant run done"
    assert activity[0].link_route == "assistant/runs"
    assert activity[0].link_id == str(run.id)
    assert route_exists(activity[0].link_route, activity[0].link_id)
    log = await client.get(run_url(run.id, "/log"), headers=headers)
    assert log.json()["run"]["status"] == "done"
    types = []
    while message := await pubsub.get_message(
        ignore_subscribe_messages=True, timeout=0.2
    ):
        types.append(message["data"])
    assert any('"run.finished"' in item for item in types)
    assert any('"text.delta"' in item for item in types)
    assert await resources.redis.smembers(f"run_delta:{run.id}:steps") == set()


async def test_cancel_of_a_waiting_run_ends_it_as_cancelled(
    client, session, resources, make_user, make_project, make_chat, make_run, queue
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await execution.begin(resources, run.id)

    await client.post(run_url(run.id, "/cancel"), headers=bearer(owner))
    resources.jobs.redis.set(f"job:{run.id}:cancel", "1")
    _, request_id, answer = queue.sent[0][1:]
    await execution.carry_on(resources, run.id, request_id, answer)

    cancelled = await reload(session, run.id)
    assert (cancelled.status, cancelled.error) == ("cancelled", None)
    assert cancelled.request is None


async def test_start_is_idempotent(
    session, resources, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    await execution.begin(resources, run.id)
    first = await RunEventRepository(session).after(run.id, -1)

    await execution.begin(resources, run.id)

    assert len(await RunEventRepository(session).after(run.id, -1)) == len(first)


async def test_a_run_that_cannot_start_fails_with_geomind_message(
    session, resources, make_user, make_project, make_chat, make_run, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ASSISTANT_LLM", "openrouter")
    monkeypatch.setenv("GEOMIND_RETRY_COUNT", "3")
    monkeypatch.setenv("GEOMIND_RETRY_DELAY", "0.5")
    use_models(monkeypatch, "deepseek/model")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    owner = await make_user()
    run = await make_run(await make_chat(await make_project(owner), owner), owner)

    await execution.begin(resources, run.id)

    failed = await reload(session, run.id)
    events = await RunEventRepository(session).after(run.id, -1, public_only=True)
    assert failed.status == "failed"
    assert failed.error["code"] == "error"
    assert "OPENROUTER_API_KEY" in failed.error["message"]
    assert [event.type for event in events] == ["run.finished"]


@pytest.mark.parametrize("loop", ["design", "compare", "tool"])
async def test_every_loop_starts_and_resumes_off_the_event_loop(
    session, resources, make_user, make_project, make_chat, make_run, monkeypatch, loop
) -> None:
    route = json.dumps({"kind": "loop", "loop": loop, "agent": "analysis_lead"})
    replies = [says(route), *[says("No case yet.") for _ in range(12)]]
    monkeypatch.setattr(
        session_adapter, "build_llm", lambda *_: gd.providers.FakeLLM(replies)
    )
    owner = await make_user()
    project = await make_project(owner)
    run = await make_run(await make_chat(project, owner), owner)

    await execution.begin(resources, run.id)
    ended = await reload(session, run.id)
    for _ in range(2):
        if ended.status != "waiting":
            break
        pending = ended.request
        answer = (
            {"approved": True}
            if pending["kind"] == "approval"
            else {"text": "Use the values in the case."}
        )
        await RunRepository(session).claim(
            run.id, "waiting", {"status": "running", "request": None}
        )
        await execution.carry_on(resources, run.id, pending["request"], answer)
        ended = await reload(session, run.id)

    assert ended.loop == loop
    message = (ended.error or {}).get("message", "")
    assert "event loop" not in message


async def test_a_paused_run_counts_toward_the_budget_of_the_next(
    session, resources, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    first = await make_run(chat, owner)
    await execution.begin(resources, first.id)
    spent = (await reload(session, first.id)).cost
    projects = ProjectRepository(session)
    await projects.set_budget(await projects.get_by_id(project.id), None, spent * 1.5)
    second = await make_run(chat, owner)

    await execution.begin(resources, second.id)
    ended = await reload(session, second.id)

    assert ended.status == "failed"
    assert "project cost budget" in ended.error["message"]


async def test_a_run_cancelled_before_it_starts_ends_as_cancelled(
    session, resources, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    run = await make_run(await make_chat(project, owner), owner)
    await control.request_cancel(JobRepository(resources.redis), str(run.id))

    await execution.begin(resources, run.id)
    ended = await reload(session, run.id)

    assert ended.status == "cancelled"
    assert ended.ended is not None
