import fakeredis
import pytest

from src.api.v1.assistant.runs import execution
from src.api.v1.assistant.runs.adapters.session import Resources
from src.api.v1.assistant.runs.services import run_channel
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.redis.repositories.job import SyncJobRepository
from src.core.settings import settings
from tests.api.v1.assistant.conftest import run_url
from tests.conftest import bearer


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
