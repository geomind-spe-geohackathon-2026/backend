import json
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Any, Literal
from uuid import UUID

from fastapi.sse import ServerSentEvent
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from src.api.v1.assistant.runs import schemas
from src.api.v1.assistant.runs.adapters.callbacks import (
    ANSWER,
    PERMISSION,
    STEP_STARTED,
    TOOL_RECORDED,
    AnswerTrail,
    ToolProblems,
    refused_finish,
)
from src.api.v1.assistant.runs.adapters.errors import LogUnavailableError
from src.api.v1.assistant.runs.adapters.replay import rebuilt, to_runlog
from src.api.v1.assistant.runs.adapters.sessions import agent_sessions, run_totals
from src.api.v1.assistant.runs.markdown import to_markdown
from src.core.assistant import schemas as shared
from src.core.assistant.errors import (
    CallNotFoundError,
    QueueUnavailableError,
    RunNotWaitingError,
)
from src.core.assistant.queue import Enqueue
from src.core.clients.postgres.models.project import Project
from src.core.assistant.settle import settled_ended
from src.core.clients.postgres.models.run import ACTIVE_RUN_STATUSES, Run
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.redis.repositories.job import JobRepository
from src.core.clients.redis.repositories.run_delta import RunDeltaRepository
from src.core.errors import ConflictError, ValidationFailedError
from src.core.geomind.windows import load_windows
from src.core.jobs import control
from src.core.pagination.page import Page, PageRequest, build_page
from src.core.sse.events import StreamEvent, channel_name
from src.core.sse.follow import follow_events, to_sse_stream

STREAM_KIND = "run"
RESUME_TASK = "assistant.runs.resume"
RUN_FINISHED = "run.finished"
STEP_LIMIT_OPTIONS = ("continue", "stop")


def run_channel(run_id: UUID) -> str:
    return channel_name(STREAM_KIND, str(run_id))


async def list_runs(
    project: Project,
    page: PageRequest,
    status: Literal["active"] | None,
    runs: RunRepository,
) -> Page:
    rows = await runs.list_page(project.id, page, active_only=status == "active")
    found = build_page(rows, page, shared.Run)
    prompts = await MessageRepository(runs.session).texts_for_runs(
        [item.id for item in found.items], "user"
    )
    found.items = [
        item.model_copy(update={"prompt": prompts.get(item.id)}) for item in found.items
    ]
    return found


def spending_of(stored: dict[str, Any]) -> shared.RunSpending:
    """Return geomind's ``sessions``, ``agents`` and ``total`` of a stored event.

    A field the event lacks, as in a log before geomind 0.4.24, stays ``None``, and
    figures that do not fit their shape are left out whole.
    """
    names = ("sessions", "agents", "total")
    try:
        return shared.RunSpending.model_validate({n: stored.get(n) for n in names})
    except ValidationError:
        return shared.RunSpending()


async def root_spending(run: Run, events: RunEventRepository) -> shared.RunSpending:
    """Return the spending of the root run's newest ``run.finished``.

    A run that has not ended, or ended before geomind summed it, has none.
    """
    for row in await events.of_type(run.id, RUN_FINISHED):
        if row.data.get("parent") is None:
            return spending_of(row.data)
    return shared.RunSpending()


def request_id_of(data: dict[str, Any]) -> Any:
    """Return the request id an event names, given as an id or as the request itself."""
    request = data.get("request")
    return request.get("id") if isinstance(request, dict) else request


async def already_answered(run: Run, request_id: str, session: Any) -> bool:
    """Tell whether a person's decision on ``request_id`` is stored and still stands (QA-081).

    A run a restart stopped after the decision asks the same request again when it resumes; the
    newer ask needs an answer, so a decision older than the newest ask of that request does not
    count (QA-264: the answer was refused with 409 and the run waited for ever).
    """
    events = RunEventRepository(session)
    decided = [
        row.sequence
        for row in await events.of_type(run.id, PERMISSION)
        if row.data.get("rule") == "user" and request_id_of(row.data) == request_id
    ]
    if not decided:
        return False
    asked = [
        row.sequence
        for row in await events.of_type(run.id, "request")
        if request_id_of(row.data) == request_id
    ]
    return not asked or max(decided) > max(asked)


async def current_request(run: Run, session: Any) -> None:
    """Make a waiting run's ``request`` its newest stored ``request`` event (QA-056).

    A waiting run pauses on the newest request of its run tree; the row kept an older one
    (request-3455 after the case lead asked request-3519), so the chat showed the old one and
    answering it failed the run. The row is corrected whenever a waiting run is read.
    """
    if run.status != "waiting":
        return
    if await settled_ended(run, session):
        return
    rows = await RunEventRepository(session).of_type(run.id, "request")
    event = rebuilt(rows[0].data) if rows else None
    if event is None:
        return
    newest = event.data()
    if newest.get("request") != (run.request or {}).get("request"):
        await RunRepository(session).update(run, {"request": newest})


async def read_run(run: Run, events: RunEventRepository) -> shared.Run:
    """Return a run with geomind's per-session and total figures when it has them."""
    await current_request(run, events.session)
    spending = await root_spending(run, events)
    return shared.Run.model_validate(run).model_copy(update=dict(spending))


async def read_call(
    run: Run, call_id: str, events: RunEventRepository
) -> schemas.RunCall:
    """Return one tool call's full stored output, the newest result of that call id."""
    for row in await events.of_type(run.id, TOOL_RECORDED):
        if row.data.get("call_id") != call_id:
            continue
        event = rebuilt(row.data)
        data = event.data() if event is not None else row.data
        return schemas.RunCall(
            call_id=call_id,
            tool=data.get("tool"),
            agent=data.get("agent"),
            status="error" if data.get("is_error") else "ok",
            source=data.get("source"),
            input=data.get("input"),
            output=data.get("output"),
        )
    raise CallNotFoundError(f"Run {run.id} has no tool call {call_id}")


async def read_log(run: Run, events: RunEventRepository) -> dict[str, Any]:
    rows = await events.after(run.id, -1)
    if not rows:
        raise ConflictError("The run has no log yet")
    try:
        return to_runlog([row.data for row in rows])
    except LogUnavailableError as error:
        raise ConflictError(str(error)) from error


AGENTS_CACHE_RUNS = 64
"""The runs whose events ``read_agents`` keeps in memory, the most recently read (QA-217)."""
_agents_cache: OrderedDict[UUID, dict[str, Any]] = OrderedDict()


async def cached_events(run: Run, events: RunEventRepository) -> dict[str, Any]:
    """Return a run's stored events, reading only the ones newer than the last read (QA-217).

    The agents view is polled every few seconds by every open tab; reading thousands of events
    on each poll held the database pool until it ran out. The rows of one sequence that came
    after a read are taken by id, so none is lost or counted twice.
    """
    entry = _agents_cache.pop(run.id, None) or {"ids": set(), "data": [], "last": -1, "answer": None}
    _agents_cache[run.id] = entry
    while len(_agents_cache) > AGENTS_CACHE_RUNS:
        _agents_cache.popitem(last=False)
    rows = await events.after(run.id, entry["last"] - 1)
    fresh = [row for row in rows if row.id not in entry["ids"]]
    for row in fresh:
        entry["ids"].add(row.id)
        entry["data"].append(row.data)
        entry["last"] = max(entry["last"], row.sequence)
    if fresh:
        entry["answer"] = None
    return entry


async def read_agents(run: Run, events: RunEventRepository) -> schemas.RunAgents:
    """Return the agent sessions of a run from the events stored so far.

    A run with no events yet has no sessions; each session's context is its own. The sessions
    are worked out again only when new events came (QA-217).
    """
    entry = await cached_events(run, events)
    if entry["answer"] is None:
        entry["answer"] = await agent_sessions(entry["data"])
    sessions, total = entry["answer"]
    totals = {"id": run.id, "status": run.status, **run_totals(sessions, total)}
    return schemas.RunAgents.model_validate({"run": totals, "agents": sessions})


async def export_log(
    run: Run,
    export_format: Literal["json", "md"],
    events: RunEventRepository,
) -> tuple[str, str, str]:
    """Return the log as text, its media type and a file name."""
    log = await read_log(run, events)
    if export_format == "json":
        return json.dumps(log, indent=2), "application/json", f"run-{run.id}.json"
    return to_markdown(log), "text/markdown", f"run-{run.id}.md"


def check_answer(pending: dict[str, Any] | None, body: schemas.RunAnswer) -> None:
    """Refuse an answer that does not fit the request the run waits for."""
    if pending is None or body.request != pending.get("request"):
        current = (pending or {}).get("request")
        message = "This is not the pending request" + (
            f"; the run waits on {current}" if current else "; the run waits on nothing"
        )
        raise ValidationFailedError({"request": message})
    expected = schemas.Approval if pending["kind"] == "approval" else schemas.Reply
    if not isinstance(body.answer, expected):
        raise ValidationFailedError({"answer": f"Expected a {pending['kind']} answer"})
    values = [item["value"] for item in pending.get("options") or ()]
    if is_step_limit(pending) and body.answer.text not in values:
        raise ValidationFailedError({"answer": "Not one of the options"})


def is_step_limit(pending: dict[str, Any]) -> bool:
    """Tell the question at a run's step limit, which takes only continue or stop.

    Any other question with options also takes the user's own typed words; geomind
    marks them as typed for the model.
    """
    values = [item["value"] for item in pending.get("options") or ()]
    return values == list(STEP_LIMIT_OPTIONS) and not pending.get("call_id")


async def hand_over(
    runs: RunRepository,
    run: Run,
    enqueue: Enqueue,
    arguments: tuple[Any, ...],
) -> None:
    """Queue the resume task; if the queue is down the run waits again."""
    pending = run.request
    running = {"status": "running", "request": None}
    claimed = await runs.claim(run.id, "waiting", running)
    if not claimed:
        raise RunNotWaitingError("Run is not waiting for an answer")
    try:
        await run_in_threadpool(enqueue, RESUME_TASK, str(run.id), *arguments)
    except QueueUnavailableError:
        await runs.claim(run.id, "running", {"status": "waiting", "request": pending})
        raise


async def answer_run(
    run: Run,
    body: schemas.RunAnswer,
    runs: RunRepository,
    enqueue: Enqueue,
) -> Run:
    """Hand the answer to the run; a run waiting on a request it already has a decision on goes
    on from its log instead (QA-264: a restart left the row waiting on an answered request, and
    every answer was refused with 409, so the run never moved again).
    """
    if run.status != "waiting":
        raise RunNotWaitingError("Run is not waiting for an answer")
    await current_request(run, runs.session)
    check_answer(run.request, body)
    if await already_answered(run, body.request, runs.session):
        await hand_over(runs, run, enqueue, (None, None))
    else:
        await hand_over(runs, run, enqueue, (body.request, body.to_dict()))
    await runs.session.refresh(run)
    return run


def cancel_answer(pending: dict[str, Any]) -> dict[str, Any]:
    """Return an answer that geomind accepts for a request about to be cancelled.

    geomind resumes only by answering the pending request; the cancellation hook
    ends the run before the answer is used.
    """
    if pending["kind"] == "approval":
        return {"approved": False, "reason": "cancelled"}
    options = pending.get("options")
    return {"text": options[0]["value"] if options else "cancelled"}


async def cancel_run(
    run: Run,
    runs: RunRepository,
    jobs: JobRepository,
    enqueue: Enqueue,
) -> Run:
    """Ask a run to stop.

    A queued or running run reads the flag at its next step. A waiting run has no
    process, so it is resumed once with a stand-in answer and ends as cancelled.
    """
    if run.status not in ACTIVE_RUN_STATUSES:
        raise ConflictError("The run has already ended")
    await control.request_cancel(jobs, str(run.id))
    if run.status == "waiting":
        await current_request(run, runs.session)
        pending = run.request
        await hand_over(
            runs, run, enqueue, (pending["request"], cancel_answer(pending))
        )
    await runs.session.refresh(run)
    return run


async def stored_events(
    factory: async_sessionmaker[AsyncSession],
    deltas: RunDeltaRepository,
    run_id: UUID,
    after: int,
) -> list[StreamEvent]:
    """Return the public events after a sequence, then the text of running steps.

    The buffered text of a step comes as one ``text.delta`` without an id and
    ``buffered: true``, after the stored events; the client replaces the step's text
    with it, and the step's ``step.finished`` replaces that.
    """
    async with factory() as session:
        rows = await RunEventRepository(session).after(
            run_id, after, public_only=True, also=(TOOL_RECORDED, PERMISSION)
        )
    problems = ToolProblems()
    answers = AnswerTrail()
    known = [(row, rebuilt(row.data)) for row in rows]
    steps = [event for _, event in known if event and event.type == STEP_STARTED]
    await load_windows(event.model for event in steps)
    events = []
    for row, event in known:
        if event is None:
            continue
        problems.note(event)
        answered = answers.note(event)
        if answered is not None:
            events.append(StreamEvent(ANSWER, answered, row.sequence))
        if row.public:
            data = problems.public(event)
            if row.type == "run.finished":
                data = refused_finish(data)
            events.append(StreamEvent(row.type, data, row.sequence))
    for delta in await deltas.pending(str(run_id)):
        data = {
            "index": delta.index,
            "text": delta.text,
            "agent": delta.agent,
            "parent": delta.parent,
            "session": delta.session,
            "buffered": True,
        }
        if delta.instance is not None:
            data["instance"] = delta.instance
        events.append(StreamEvent("text.delta", data, None))
    return events


def ends_the_run(event: StreamEvent) -> bool:
    return event.type == RUN_FINISHED and event.data.get("parent") is None


async def follow_run_events(
    run_id: UUID,
    redis: Redis,
    factory: async_sessionmaker[AsyncSession],
    after: int,
) -> AsyncIterator[StreamEvent | None]:
    """Yield a run: stored events after ``after``, buffered text, then live events.

    It ends after the root run's ``run.finished``; the run finished events of delegated
    runs do not end it. ``None`` marks a quiet interval.
    """
    deltas = RunDeltaRepository(redis)

    async def replay(sequence: int) -> list[StreamEvent]:
        return await stored_events(factory, deltas, run_id, sequence)

    stream = follow_events(redis, run_channel(run_id), replay, after, final_types=())
    async with aclosing(stream):
        async for event in stream:
            yield event
            if event is not None and ends_the_run(event):
                return


def follow_run(
    run_id: UUID,
    redis: Redis,
    factory: async_sessionmaker[AsyncSession],
    after: int,
) -> AsyncIterator[ServerSentEvent]:
    """Stream a run over SSE; see ``follow_run_events``."""
    return to_sse_stream(follow_run_events(run_id, redis, factory, after))
