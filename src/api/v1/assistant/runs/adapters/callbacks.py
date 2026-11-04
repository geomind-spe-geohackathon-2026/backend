import re
from typing import Any
from uuid import UUID

import geomind as gd
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.run_artifact import (
    RunArtifactRepository,
)
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.clients.redis.models.run_delta import PendingDelta
from src.core.clients.redis.repositories.run_delta import RunDeltaRepository
from src.core.geomind.windows import window_of
from src.core.routes import STUDY_ROUTE
from src.core.sse.events import StreamEvent
from src.core.sse.publish import publish_event_async

TERMINAL_STATUSES = ("done", "failed", "cancelled")
TEXT_DELTA = "text.delta"
TOOL_RECORDED = "tool.result"
TOOL_FINISHED = "tool.finished"
STEP_STARTED = "step.started"
STEP_FINISHED = "step.finished"
STUDY_RECORDED = "study.recorded"
STUDY_PREFIX = "study/"
AGENT_NAME = "Assistant"
RETRY = "retry"
STATUS = re.compile(r"status = (\d{3})")


def retry_notice(event: Any) -> dict[str, Any]:
    """Return the live ``retry`` notice of a failed provider call (QA-021).

    geomind's ``retry`` event is internal; the chat showed only Thinking while the provider
    refused every call. The notice says that the provider is retried and when; it carries the
    HTTP status only, never the provider's text.
    """
    found = STATUS.search(str(getattr(event, "error", "") or ""))
    return {
        "agent": event.agent,
        "parent": event.parent,
        "attempt": event.attempt,
        "model": event.model,
        "delay": event.delay,
        "status": int(found.group(1)) if found else None,
    }


class ToolProblems:
    """Add the structured problem of a failed tool to its public ``tool.finished``.

    geomind's public event holds a cut text; the whole problem is in the internal
    ``tool.result`` that comes right before it, with the code and the missing paths.
    """

    def __init__(self) -> None:
        self.found: dict[tuple[str, str], dict[str, Any]] = {}

    def note(self, event: Any) -> None:
        """Keep the problem of a recorded tool result."""
        problem = problem_of(event)
        if problem is not None:
            self.found[(event.agent, event.call_id)] = problem

    def public(self, event: Any) -> dict[str, Any]:
        """Return an event's public data, with its problem when it has one.

        A ``step.started`` also says the context window of the model on that step:
        geomind's own when it sends one, else the window looked up for the model.
        """
        data = event.data()
        if event.type == STEP_STARTED and data.get("context_window") is None:
            window = window_of(getattr(event, "model", None))
            return data if window is None else {**data, "context_window": window}
        if event.type != TOOL_FINISHED:
            return data
        problem = self.found.pop((event.agent, event.call_id), None)
        return data if problem is None else {**data, "problem": problem}


def problem_of(event: Any) -> dict[str, Any] | None:
    """Return a failed tool's problem, or ``None`` when its output has no code."""
    if event.type != TOOL_RECORDED or not event.is_error:
        return None
    output = event.output if isinstance(event.output, dict) else {}
    error = output.get("error")
    if not isinstance(error, dict) or not isinstance(error.get("code"), str):
        return None
    return {
        "code": error["code"],
        "path": error.get("path"),
        "message": error.get("message", ""),
        "suggestions": list(error.get("suggestions") or ()),
    }


class EventPublisher(gd.callbacks.Callback):
    """Send the public events of a run to the browser through Redis.

    geomind saves an event before it tells the callbacks, so a stored event is already
    in the database when it is published. A ``text.delta`` is never stored; it is
    kept in a short-lived buffer for reconnects until its step finishes.
    """

    def __init__(self, redis: Redis, channel: str, run_id: UUID, ttl: int) -> None:
        self.redis = redis
        self.channel = channel
        self.run_id = str(run_id)
        self.ttl = ttl
        self.deltas = RunDeltaRepository(redis)
        self.problems = ToolProblems()

    async def on_event(self, engine: Any, event: Any) -> None:
        """Publish one event if it is public."""
        self.problems.note(event)
        if event.type == RETRY:
            notice = StreamEvent(RETRY, retry_notice(event), None)
            await publish_event_async(self.redis, self.channel, notice)
            return
        if not event.is_public:
            return
        if event.type == TEXT_DELTA:
            await self.buffer(event)
            sequence = None
        else:
            await self.forget(event)
            sequence = event.sequence
        stream_event = StreamEvent(event.type, self.problems.public(event), sequence)
        await publish_event_async(self.redis, self.channel, stream_event)

    async def buffer(self, event: Any) -> None:
        delta = PendingDelta(event.agent, event.parent, event.index, event.text)
        await self.deltas.append(self.run_id, delta, self.ttl)

    async def forget(self, event: Any) -> None:
        if event.type != STEP_FINISHED:
            return
        await self.deltas.clear(self.run_id, event.agent, event.parent, event.index)


async def set_values(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    values: dict[str, Any],
) -> None:
    async with factory() as session:
        run = await RunRepository(session).get_by_id(run_id)
        if run is not None:
            await RunRepository(session).update(run, values)


def usage_columns(event: Any) -> dict[str, Any]:
    return {
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "cost": event.cost,
    }


def finish_columns(event: Any) -> dict[str, Any]:
    values: dict[str, Any] = {"status": event.status, "request": None}
    if event.status in TERMINAL_STATUSES:
        values["ended"] = utc_now()
    if event.status == "failed":
        values["error"] = {"code": event.stop_reason, "message": event.message or ""}
    return values


class RunRecorder(gd.callbacks.Callback):
    """Keep the run's row current while the run goes.

    It is listed before the publisher, so a client that receives ``request`` or
    ``run.finished`` finds the row already in that state. It follows the root run for
    its loop, running totals and end; a request of any agent makes the run wait.
    """

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        run_id: UUID,
    ) -> None:
        self.factory = factory
        self.run_id = run_id

    async def on_event(self, engine: Any, event: Any) -> None:
        """Write the columns an event changes."""
        values = self.columns(event)
        if values:
            await set_values(self.factory, self.run_id, values)

    def columns(self, event: Any) -> dict[str, Any]:
        if event.type == "request":
            return {"status": "waiting", "request": event.data()}
        if event.parent is not None:
            return {}
        if event.type == "run.started" and event.loop is not None:
            return {"loop": event.loop}
        if event.type == "usage":
            return usage_columns(event)
        if event.type == "run.finished":
            return finish_columns(event)
        return {}


class StudyRecorder(gd.callbacks.Callback):
    """Add a study the assistant ran to the project's study list.

    geomind stores the study artifact before it sends ``study.recorded``. The row
    has no Celery job and no result of its own: it ended before it was listed.
    """

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        run_id: UUID,
        chat_id: UUID,
        project_id: UUID,
    ) -> None:
        self.factory = factory
        self.run_id = run_id
        self.chat_id = chat_id
        self.project_id = project_id

    async def on_event(self, engine: Any, event: Any) -> None:
        """Add the row of a recorded study."""
        if event.type != STUDY_RECORDED:
            return
        async with self.factory() as session:
            artifact = await RunArtifactRepository(session).newest_for_chat(
                self.chat_id, event.study
            )
            case = await CaseVersionRepository(session).latest_version(self.project_id)
            study = await StudyRepository(session).create(
                self.values(event, artifact, case)
            )
            await ActivityRepository(session).add(
                self.project_id,
                "agent",
                "assistant",
                f"Study {study.name} recorded",
                STUDY_ROUTE,
                str(study.id),
            )

    def values(self, event: Any, artifact: Any, case: Any) -> dict[str, Any]:
        now = utc_now()
        return {
            "project_id": self.project_id,
            "kind": event.method,
            "name": event.study.removeprefix(STUDY_PREFIX),
            "settings": {} if artifact is None else artifact.data["study"],
            "status": "done",
            "started_by_kind": "agent",
            "started_by_name": AGENT_NAME,
            "started_by_run_id": self.run_id,
            "case_version": None if case is None else case.number,
            "plant_version": None,
            "started": now,
            "ended": now,
        }
