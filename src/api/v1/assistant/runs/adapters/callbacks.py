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
from src.core.clients.postgres.repositories.result import ResultRepository
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


PERMISSION = "permission"
ANSWER = "answer"


class AnswerTrail:
    """Turn a person's decision on a request into a public ``answer`` event (QA-058).

    geomind records it only in the internal ``permission`` event (``rule: user``) and, for a
    typed answer, in the ``tool.result`` with ``source: answer``; the chat could not show it after
    a reload. ``note`` returns the ``answer`` data, or ``None``, for each event in order.
    """

    def __init__(self) -> None:
        self.typed: dict[str, dict[str, Any]] = {}

    def note(self, event: Any) -> dict[str, Any] | None:
        if event.type == PERMISSION:
            data = event.data()
            if data.get("rule") != "user":
                return None
            notice = answer_data(data)
            if notice["time"] is None and getattr(event, "time", None) is not None:
                stamp = event.time
                notice["time"] = (stamp.isoformat() if hasattr(stamp, "isoformat") else str(stamp)) or None
            if data.get("decision") == "answer" and data.get("call_id"):
                self.typed[data["call_id"]] = notice
                return None
            return notice
        if event.type == TOOL_RECORDED and getattr(event, "source", None) == "answer":
            notice = self.typed.pop(getattr(event, "call_id", None) or "", None)
            if notice is None:
                return None
            output = getattr(event, "output", None)
            text = output.get("answer") if isinstance(output, dict) else output
            return {**notice, "text": None if text is None else str(text)}
        return None


def answer_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return the public ``answer`` fields of a user's ``permission`` decision."""
    request = data.get("request") or {}
    if not isinstance(request, dict):
        request = {}
    return {
        "agent": data.get("agent"),
        "parent": data.get("parent"),
        "request": request.get("id") or request.get("request"),
        "kind": request.get("kind"),
        "message": request.get("message"),
        "tool": data.get("tool"),
        "call_id": data.get("call_id"),
        "decision": data.get("decision"),
        "reason": data.get("reason"),
        "text": None,
        "by": "user",
        "time": data.get("time"),
    }


USAGE = "usage"
USAGE_KEYS = ("input_tokens", "output_tokens", "cost")


class UsageTree:
    """The run tree's running totals while nested runs go (QA-046).

    geomind's ``usage`` of the root run counts a nested run only after the nested run ends, so
    the run's total stayed flat for minutes and then jumped. A nested run sends its own running
    totals; the tree's total is the root's last totals plus the latest of each nested run whose
    parent is the root, until the root's next ``usage`` (which then holds them).
    """

    def __init__(self, run_id: UUID) -> None:
        self.root = run_id.hex
        self.base: dict[str, Any] | None = None
        self.children: dict[str, dict[str, Any]] = {}

    def add(self, event: Any) -> dict[str, Any] | None:
        """Take a ``usage`` event; return the tree's totals when a nested one changed them."""
        totals = {key: getattr(event, key, 0) or 0 for key in USAGE_KEYS}
        if event.parent is None:
            self.base = totals
            self.children = {}
            return None
        if str(event.parent).replace("-", "") != self.root or self.base is None:
            return None
        self.children[str(event.agent)] = totals
        return {
            key: self.base[key] + sum(child[key] for child in self.children.values())
            for key in USAGE_KEYS
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
        self.usage = UsageTree(run_id)
        self.root_agent = ""
        self.answers = AnswerTrail()

    async def on_event(self, engine: Any, event: Any) -> None:
        """Publish one event if it is public."""
        self.problems.note(event)
        answered = self.answers.note(event)
        if answered is not None:
            await publish_event_async(
                self.redis, self.channel, StreamEvent(ANSWER, answered, event.sequence)
            )
        if event.type == USAGE:
            totals = self.usage.add(event)
            if totals is not None:
                tree = {"agent": self.root_agent, "parent": None, **totals}
                await publish_event_async(
                    self.redis, self.channel, StreamEvent(USAGE, tree, None)
                )
        if event.parent is None and getattr(event, "agent", None):
            self.root_agent = event.agent
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
        data = self.problems.public(event)
        if event.type == "run.finished":
            data = refused_finish(data)
        stream_event = StreamEvent(event.type, data, sequence)
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
    """Write the values to the run row.

    An ended run never goes back to running or waiting: its status and request stay (QA-077, a
    late request event set a failed run to waiting, and its chat refused every new message).
    """
    async with factory() as session:
        run = await RunRepository(session).get_by_id(run_id)
        if run is None:
            return
        if run.status in TERMINAL_STATUSES and values.get("status") not in TERMINAL_STATUSES:
            values = {k: v for k, v in values.items() if k not in ("status", "request")}
            if not values:
                return
        await RunRepository(session).update(run, values)


def usage_columns(event: Any) -> dict[str, Any]:
    return {
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "cost": event.cost,
    }


PROVIDER_REFUSED = "provider_refused"
PROVIDER_STATUS = re.compile(r"status = (401|402|403|429)\b")


def provider_refusal(message: str | None) -> str | None:
    """Return a clear message for a model provider's quota or key refusal, else ``None``.

    geomind ends such a run with ``stop_reason: error`` and the provider's text, which the chat
    showed as "an internal error in geomind" (QA-068: OpenRouter 403 "Key limit exceeded").
    """
    found = PROVIDER_STATUS.search(message or "")
    if found is None:
        return None
    status = found.group(1)
    text = message or ""
    if status == "403" and "limit" in text.lower():
        return "The model provider refused: key limit exceeded; an admin must raise it."
    if status == "402":
        return "The model provider refused: no credits left (402); an admin must add credits."
    if status == "401":
        return "The model provider refused the API key (401); an admin must check it."
    if status == "429":
        return (
            "The model provider kept refusing with too many requests (429); try again in a few "
            "minutes."
        )
    return f"The model provider refused the request (403): {text[:300]}"


def refused_finish(data: dict[str, Any]) -> dict[str, Any]:
    """Return ``run.finished`` data with a provider refusal named as such (QA-068)."""
    if data.get("status") != "failed":
        return data
    clear = provider_refusal(data.get("message"))
    if clear is None:
        return data
    return {**data, "stop_reason": PROVIDER_REFUSED, "message": clear}


def finish_columns(event: Any) -> dict[str, Any]:
    values: dict[str, Any] = {"status": event.status, "request": None}
    if event.status in TERMINAL_STATUSES:
        values["ended"] = utc_now()
    if event.status == "failed":
        clear = provider_refusal(event.message)
        values["error"] = (
            {"code": PROVIDER_REFUSED, "message": clear}
            if clear
            else {"code": event.stop_reason, "message": event.message or ""}
        )
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
        self.usage = UsageTree(run_id)

    async def on_event(self, engine: Any, event: Any) -> None:
        """Write the columns an event changes."""
        values = self.columns(event)
        if values:
            await set_values(self.factory, self.run_id, values)

    def columns(self, event: Any) -> dict[str, Any]:
        if event.type == "request":
            return {"status": "waiting", "request": event.data()}
        if event.type == USAGE:
            totals = self.usage.add(event)
            if totals is not None:
                return totals
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
            await self.add_results(session, study, artifact, case)
            await ActivityRepository(session).add(
                self.project_id,
                "agent",
                "assistant",
                f"Study {study.name} recorded",
                STUDY_ROUTE,
                str(study.id),
            )

    async def add_results(self, session: Any, study: Any, artifact: Any, case: Any) -> None:
        """Add a result row per simulated run of an agent study, as a page study has (QA-088).

        geomind 0.4.77 stores ``runs`` in the ``study/<name>`` artifact: each with the full
        gemini ``report``, its ``run`` and a ``design`` reference; coverage is computed on the
        first read, as for a page study. An entry with an ``error`` or no report is skipped.
        """
        from src.core.gemini import evaluate as gemini_evaluate

        runs = (artifact.data.get("runs") if artifact is not None else None) or []
        simulated = [item for item in runs if isinstance(item, dict) and item.get("report")]
        artifacts = RunArtifactRepository(session)
        results = ResultRepository(session)
        for item in simulated:
            reference = item.get("design")
            design = (
                await artifacts.newest_for_chat(self.chat_id, reference) if reference else None
            )
            parts = gemini_evaluate.summarise(item["report"])
            name = study.name
            if len(simulated) > 1 and item.get("plant_name"):
                name = f"{study.name} {item['plant_name']}"
            await results.create(
                {
                    "project_id": self.project_id,
                    "study_id": study.id,
                    "name": name,
                    "case_version": None if case is None else case.number,
                    "plant_version": None,
                    "summary": parts["summary"],
                    "content": {
                        "capacities": parts["capacities"],
                        "constraints": parts["constraints"],
                        "series": [],
                        "report": item["report"],
                        "run": item.get("run") or {},
                        "design": None if design is None else design.data,
                        "coverage": None,
                    },
                }
            )

    def values(self, event: Any, artifact: Any, case: Any) -> dict[str, Any]:
        """Give the study row of a recorded study.

        A recorded study ended before it was listed, so its progress is 1 of 1, not the default
        0 of 1 the list showed as "-" (QA-088).
        """
        now = utc_now()
        return {
            "project_id": self.project_id,
            "kind": event.method,
            "name": event.study.removeprefix(STUDY_PREFIX),
            "settings": {} if artifact is None else artifact.data["study"],
            "status": "done",
            "progress_done": 1,
            "progress_total": 1,
            "started_by_kind": "agent",
            "started_by_name": AGENT_NAME,
            "started_by_run_id": self.run_id,
            "case_version": None if case is None else case.number,
            "plant_version": None,
            "started": now,
            "ended": now,
        }
