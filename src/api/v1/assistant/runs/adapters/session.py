import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import geomind as gd
from minio import Minio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge
from src.api.v1.assistant.runs.adapters.callbacks import EventPublisher, RunRecorder
from src.api.v1.assistant.runs.adapters.errors import AdapterFailedError
from src.api.v1.assistant.runs.adapters.fake import scripted_llm
from src.api.v1.assistant.runs.adapters.store import DatabaseRunStore
from src.api.v1.assistant.runs.adapters.workspace import DatabaseWorkspace
from src.core.clients.redis.repositories.job import SyncJobRepository
from src.core.settings import settings


@dataclass(frozen=True)
class Resources:
    """The connections a worker opens for one task."""

    factory: async_sessionmaker[AsyncSession]
    redis: Redis
    jobs: SyncJobRepository
    minio: Minio


@dataclass(frozen=True)
class Environment:
    """What a run needs from the backend: its store, workspace, callbacks and flag."""

    store: DatabaseRunStore
    workspace: DatabaseWorkspace
    callbacks: list[Any]
    is_cancelled: Callable[[], bool]


@dataclass(frozen=True)
class Outcome:
    """How a run ended or paused; ``answer`` is text, empty when there is none."""

    status: str
    stop_reason: str | None
    answer: str
    input_tokens: int
    output_tokens: int
    cost: float


@dataclass(frozen=True)
class EventRecord:
    """An event the backend writes itself: one of geomind's, built from a dict."""

    sequence: int
    type: str
    public: bool
    full: dict[str, Any]
    data: dict[str, Any]


def build_environment(
    resources: Resources,
    folder: Path,
    run: Any,
    channel: str,
) -> Environment:
    """Connect a run row to geomind: store, workspace and the two callbacks.

    The recorder comes first, so the row is current before the event is published.
    """
    bridge = LoopBridge(asyncio.get_running_loop(), resources.factory)
    recorder = RunRecorder(resources.factory, run.id)
    publisher = EventPublisher(
        resources.redis,
        channel,
        run.id,
        settings.ASSISTANT_DELTA_TTL_SECONDS,
    )
    return Environment(
        store=DatabaseRunStore(bridge, run.id, run.chat_id),
        workspace=DatabaseWorkspace(bridge, resources.minio, folder),
        callbacks=[recorder, publisher],
        is_cancelled=lambda: resources.jobs.is_cancel_requested(str(run.id)),
    )


def build_llm(resumed: bool) -> Any:
    if settings.ASSISTANT_LLM == "fake":
        return scripted_llm(resumed)
    return gd.providers.OpenRouter(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )


def build_hooks(environment: Environment) -> list[Any]:
    return [
        gd.hooks.TokenBudget(settings.ASSISTANT_RUN_MAX_TOKENS),
        gd.hooks.Cancellation(environment.is_cancelled),
    ]


def build_sandbox() -> Any:
    if settings.ASSISTANT_SANDBOX == "docker":
        return gd.sandbox.DockerSandbox()
    return None


def build_permissions() -> Any:
    return gd.Permissions(mode="ask")


def answer_text(answer: Any) -> str:
    if answer is None:
        return ""
    if isinstance(answer, str):
        return answer
    return json.dumps(answer, ensure_ascii=False, default=str)


def to_outcome(result: Any) -> Outcome:
    return Outcome(
        status=result.status,
        stop_reason=result.stop_reason,
        answer=answer_text(result.answer),
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cost=result.usage.cost,
    )


def keywords(environment: Environment, resumed: bool) -> dict[str, Any]:
    return {
        "llm": build_llm(resumed),
        "store": environment.store,
        "workspace": environment.workspace,
        "sandbox": build_sandbox(),
        "permissions": build_permissions(),
        "callbacks": environment.callbacks,
        "hooks": build_hooks(environment),
    }


async def start(
    environment: Environment,
    run_id: UUID,
    chat_id: UUID,
    project_id: UUID,
    message: str,
) -> Outcome:
    """Start a run under the id the backend gave it; geomind chooses loop and agent."""
    history = await asyncio.to_thread(environment.store.load_history, str(chat_id))
    try:
        run = gd.Run(
            message=message,
            chat=str(chat_id),
            project=str(project_id),
            history=history,
            **keywords(environment, resumed=False),
        )
        run.id = run_id.hex
        return to_outcome(await run.astart())
    except gd.errors.GeomindError as error:
        raise AdapterFailedError(str(error)) from error


async def resume(
    environment: Environment,
    run_id: UUID,
    request_id: str | None,
    answer: dict[str, Any] | None,
) -> Outcome:
    """Answer a pending request, or with none continue a run that was cancelled."""
    try:
        await environment.store.warm(run_id.hex)
        run = await asyncio.to_thread(
            gd.Run.load,
            run_id.hex,
            **keywords(environment, resumed=True),
        )
        return to_outcome(await run.aresume(request_id, answer))
    except gd.errors.GeomindError as error:
        raise AdapterFailedError(str(error)) from error


def failure_event(run_id: UUID, sequence: int, message: str) -> EventRecord:
    """Build the ``run.finished`` of a run that crashed before geomind could end it."""
    event = gd.event_from_dict(
        {
            "type": "run.finished",
            "run_id": run_id.hex,
            "sequence": sequence,
            "time": datetime.now(UTC).isoformat(),
            "agent": "",
            "parent": None,
            "status": "failed",
            "stop_reason": "error",
            "message": message,
        }
    )
    return EventRecord(
        sequence=event.sequence,
        type=event.type,
        public=event.is_public,
        full=event.to_dict(),
        data=event.data(),
    )
