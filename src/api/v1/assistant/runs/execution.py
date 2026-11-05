from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from uuid import UUID

from redis import Redis as SyncRedis
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.api.v1.assistant.runs.adapters import session as adapters
from src.api.v1.assistant.runs.adapters.callbacks import (
    PROVIDER_REFUSED,
    TERMINAL_STATUSES,
    provider_refusal,
    refused_finish,
)
from src.api.v1.assistant.runs.adapters.errors import (
    AdapterFailedError,
    StaleRequestError,
)
from src.api.v1.assistant.runs.services import run_channel
from src.core.clients.minio.client import create_minio_client
from src.core.clients.postgres.client import create_postgres_client, utc_now
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.redis.client import create_redis_client
from src.core.clients.redis.repositories.job import SyncJobRepository
from src.core.logging.logger import get_logger
from src.core.routes import RUNS_ROUTE
from src.core.settings import settings
from src.core.sse.events import StreamEvent
from src.core.sse.publish import publish_event_async

logger = get_logger(__name__)

Action = Callable[[adapters.Environment], Awaitable[adapters.Outcome]]


@asynccontextmanager
async def open_resources() -> AsyncIterator[adapters.Resources]:
    """Open the connections of one task and close them when it ends."""
    engine = create_postgres_client()
    redis = create_redis_client()
    sync_redis = SyncRedis.from_url(settings.REDIS_URL, decode_responses=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    jobs = SyncJobRepository(sync_redis, settings.JOB_STATE_TTL_SECONDS)
    try:
        yield adapters.Resources(factory, redis, jobs, create_minio_client())
    finally:
        sync_redis.close()
        await redis.aclose()
        await engine.dispose()


async def start_run(run_id: UUID) -> None:
    """Task body: run a queued run."""
    async with open_resources() as resources:
        await begin(resources, run_id)


async def resume_run(
    run_id: UUID,
    request_id: str | None,
    answer: dict[str, Any] | None,
) -> None:
    """Task body: continue a run after an answer, or after a cancel while waiting."""
    async with open_resources() as resources:
        await carry_on(resources, run_id, request_id, answer)


GEOMIND_REFUSED = "geomind_refused"
"""The stop reason of a run geomind refused to build or go on with; its message is geomind's."""
INTERRUPTED = (
    "The run stopped because the app was updated or restarted; send your message again."
)
"""What a run left ``running`` too long ago by a stopped worker says (QA-017)."""
RESUME_WITHIN = timedelta(hours=12)
"""A run left ``running`` that started within this is resumed from its log (QA-035)."""


async def interrupted_runs() -> list[UUID]:
    """Return the runs a stopped worker left ``running`` that should go on; end the others.

    A deploy or restart stops the worker and every run in it (QA-017). geomind rebuilds a run
    from its event log, and ``aresume`` with no request continues a run whose process died, so a
    run that started within ``RESUME_WITHIN`` is returned to be resumed (QA-035); an older one is
    ended as failed with a message. Queued runs stay: the broker delivers their task again.
    Waiting runs stay: they have no process until an answer resumes them.
    """
    resume = []
    async with open_resources() as resources:
        async with resources.factory() as session:
            runs = await RunRepository(session).with_status("running")
        for run in runs:
            if run.started is not None and utc_now() - run.started < RESUME_WITHIN:
                logger.warning("Run %s was running when the worker started; resuming it", run.id)
                resume.append(run.id)
                continue
            logger.warning("Run %s was running when the worker started; ending it", run.id)
            await fail(resources, run, "interrupted", INTERRUPTED)
    return resume


async def get_run(resources: adapters.Resources, run_id: UUID) -> Run | None:
    async with resources.factory() as session:
        return await RunRepository(session).get_by_id(run_id)


async def begin(resources: adapters.Resources, run_id: UUID) -> None:
    """Start a run that is still queued; a second delivery of the task does nothing."""
    values = {"status": "running", "started": utc_now()}
    async with resources.factory() as session:
        claimed = await RunRepository(session).claim(run_id, "queued", values)
    if not claimed:
        return
    run = await get_run(resources, run_id)

    async def action(environment: adapters.Environment) -> adapters.Outcome:
        async with resources.factory() as session:
            message = await MessageRepository(session).for_run(run_id, "user")
        return await adapters.start(
            environment, run.id, run.chat_id, run.project_id, message.content
        )

    await carry_out(resources, run, action)


async def carry_on(
    resources: adapters.Resources,
    run_id: UUID,
    request_id: str | None,
    answer: dict[str, Any] | None,
) -> None:
    run = await get_run(resources, run_id)
    if run is None or run.status != "running":
        return

    async def action(environment: adapters.Environment) -> adapters.Outcome:
        return await adapters.resume(environment, run_id, request_id, answer)

    await carry_out(resources, run, action)


async def read_budget(resources: adapters.Resources, run: Run) -> dict[str, Any]:
    """Return the caps of the run's project; an unset cap is none."""
    async with resources.factory() as session:
        project = await ProjectRepository(session).get_by_id(run.project_id)
    return {
        "max_tokens": project.budget_max_tokens,
        "max_cost": project.budget_max_cost,
    }


async def carry_out(
    resources: adapters.Resources,
    run: Run,
    action: Action,
) -> None:
    """Run the action and record how the run ended."""
    budget = await read_budget(resources, run)
    environment = adapters.build_environment(
        resources, run, run_channel(run.id), budget
    )
    try:
        outcome = await action(environment)
    except StaleRequestError as error:
        await wait_again(resources, run, error.expected)
        return
    except AdapterFailedError as error:
        # geomind refused to build or go on with the run (QA-081: shown as an internal error,
        # with nothing in the worker log); name it and log geomind's words.
        logger.warning("Run %s: geomind refused: %s", run.id, error)
        await fail(resources, run, GEOMIND_REFUSED, str(error))
        return
    except Exception:
        logger.exception("Run %s failed unexpectedly", run.id)
        await fail(resources, run, "internal", "The run failed unexpectedly")
        return
    await settle(resources, run.id, outcome)


async def wait_again(resources: adapters.Resources, run: Run, expected: str) -> None:
    """Put a run back to wait on geomind's pending request after an answer to another one.

    The row could name an older request than the one geomind waits on (parallel or nested
    agents), the user answered that one and the run failed (QA-056). Now the run waits again on
    the pending request, read from its stored ``request`` event, and the chat gets it again.
    """
    async with resources.factory() as session:
        stored = await RunEventRepository(session).of_type(run.id, "request")
        found = None
        for row in stored:
            event = adapters.gd.event_from_dict(row.data)
            if event.data().get("request") == expected:
                found = (row, event)
                break
        runs = RunRepository(session)
        current = await runs.get_by_id(run.id)
        if current is None or current.status in TERMINAL_STATUSES:
            return
        if found is None:
            logger.warning("Run %s waits on %s, which has no stored request", run.id, expected)
            await runs.update(current, {"status": "waiting"})
            return
        row, event = found
        await runs.update(current, {"status": "waiting", "request": event.data()})
    logger.warning("Run %s answered a stale request; waiting again on %s", run.id, expected)
    stream = StreamEvent(row.type, event.data(), row.sequence)
    await publish_event_async(resources.redis, run_channel(run.id), stream)


async def settle(
    resources: adapters.Resources,
    run_id: UUID,
    outcome: adapters.Outcome,
) -> None:
    """Write the final totals, the assistant's message and the activity row."""
    totals = {
        "input_tokens": outcome.input_tokens,
        "output_tokens": outcome.output_tokens,
        "cost": outcome.cost,
    }
    async with resources.factory() as session:
        runs = RunRepository(session)
        run = await runs.update(await runs.get_by_id(run_id), totals)
        if outcome.status == "done" and outcome.answer:
            await MessageRepository(session).add(
                run.chat_id, "assistant", outcome.answer, run.id, outcome.suggestions
            )
        if outcome.status in TERMINAL_STATUSES:
            await add_activity(session, run, outcome.status)


async def add_activity(session: Any, run: Run, status: str) -> None:
    await ActivityRepository(session).add(
        run.project_id,
        "agent",
        "assistant",
        f"Assistant run {status}",
        RUNS_ROUTE,
        str(run.id),
    )


async def fail(
    resources: adapters.Resources,
    run: Run,
    code: str,
    message: str,
) -> None:
    """End a run that crashed: log and publish its ``run.finished``, then mark it."""
    async with resources.factory() as session:
        events = RunEventRepository(session)
        last = await events.after(run.id, -1)
        sequence = last[-1].sequence + 1 if last else 1
        record = adapters.failure_event(run.id, sequence, message, code)
        await events.add(
            run.id, record.sequence, record.type, record.public, record.full
        )
        runs = RunRepository(session)
        values = {
            "status": "failed",
            "request": None,
            "ended": utc_now(),
            "error": {"code": code, "message": message},
        }
        clear = provider_refusal(message)
        if clear:
            values["error"] = {"code": PROVIDER_REFUSED, "message": clear}
        failed = await runs.update(await runs.get_by_id(run.id), values)
        await add_activity(session, failed, "failed")
    event = StreamEvent(record.type, refused_finish(record.data), record.sequence)
    await publish_event_async(resources.redis, run_channel(run.id), event)
