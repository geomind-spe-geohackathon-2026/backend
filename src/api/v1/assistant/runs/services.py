import json
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Any, Literal
from uuid import UUID

from fastapi.sse import ServerSentEvent
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from src.api.v1.assistant.runs import schemas
from src.api.v1.assistant.runs.adapters.errors import LogUnavailableError
from src.api.v1.assistant.runs.adapters.replay import to_public, to_runlog
from src.api.v1.assistant.runs.markdown import to_markdown
from src.core.assistant import schemas as shared
from src.core.assistant.errors import QueueUnavailableError, RunNotWaitingError
from src.core.assistant.queue import Enqueue
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.run import ACTIVE_RUN_STATUSES, Run
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.redis.repositories.job import JobRepository
from src.core.clients.redis.repositories.run_delta import RunDeltaRepository
from src.core.errors import ConflictError, ValidationFailedError
from src.core.jobs import control
from src.core.pagination.page import Page, PageRequest, build_page
from src.core.sse.events import StreamEvent, channel_name
from src.core.sse.follow import follow

STREAM_KIND = "run"
RESUME_TASK = "assistant.runs.resume"


def run_channel(run_id: UUID) -> str:
    return channel_name(STREAM_KIND, str(run_id))


async def list_runs(
    project: Project,
    page: PageRequest,
    status: Literal["active"] | None,
    runs: RunRepository,
) -> Page:
    rows = await runs.list_page(project.id, page, active_only=status == "active")
    return build_page(rows, page, shared.Run)


async def read_log(run: Run, events: RunEventRepository) -> dict[str, Any]:
    rows = await events.after(run.id, -1)
    if not rows:
        raise ConflictError("The run has no log yet")
    try:
        return to_runlog([row.data for row in rows])
    except LogUnavailableError as error:
        raise ConflictError(str(error)) from error


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
        raise ValidationFailedError({"request": "This is not the pending request"})
    expected = schemas.Approval if pending["kind"] == "approval" else schemas.Reply
    if not isinstance(body.answer, expected):
        raise ValidationFailedError({"answer": f"Expected a {pending['kind']} answer"})
    options = pending.get("options")
    if options and body.answer.text not in [item["value"] for item in options]:
        raise ValidationFailedError({"answer": "Not one of the options"})


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
    if run.status != "waiting":
        raise RunNotWaitingError("Run is not waiting for an answer")
    check_answer(run.request, body)
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
        rows = await RunEventRepository(session).after(run_id, after, public_only=True)
    events = [StreamEvent(row.type, to_public(row.data), row.sequence) for row in rows]
    for delta in await deltas.pending(str(run_id)):
        data = {
            "index": delta.index,
            "text": delta.text,
            "agent": delta.agent,
            "parent": delta.parent,
            "buffered": True,
        }
        events.append(StreamEvent("text.delta", data, None))
    return events


def ends_the_run(item: ServerSentEvent) -> bool:
    return (
        item.event == "run.finished"
        and isinstance(item.data, dict)
        and item.data.get("parent") is None
    )


async def follow_run(
    run_id: UUID,
    redis: Redis,
    factory: async_sessionmaker[AsyncSession],
    after: int,
) -> AsyncIterator[ServerSentEvent]:
    """Stream a run: stored events after ``after``, buffered text, then live events.

    The stream ends after the root run's ``run.finished``; the run finished events of
    delegated runs do not end it.
    """
    deltas = RunDeltaRepository(redis)

    async def replay(sequence: int) -> list[StreamEvent]:
        return await stored_events(factory, deltas, run_id, sequence)

    stream = follow(redis, run_channel(run_id), replay, after, final_types=())
    async with aclosing(stream):
        async for item in stream:
            yield item
            if ends_the_run(item):
                return
