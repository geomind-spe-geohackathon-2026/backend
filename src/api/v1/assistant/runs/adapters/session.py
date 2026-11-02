import asyncio
import copy
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import geomind as gd
from minio import Minio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge
from src.api.v1.assistant.runs.adapters.callbacks import (
    EventPublisher,
    RunRecorder,
    StudyRecorder,
)
from src.api.v1.assistant.runs.adapters.errors import AdapterFailedError
from src.api.v1.assistant.runs.adapters.fake import scripted_llm
from src.api.v1.assistant.runs.adapters.store import (
    DatabaseRunStore,
    DatabaseUsageLedger,
)
from src.api.v1.assistant.runs.adapters.workspace import DatabaseWorkspace
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.redis.repositories.job import SyncJobRepository
from src.core.gemini import case as gemini_case
from src.core.settings import settings

CASE_ARTIFACT = "case/"


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
    ledger: DatabaseUsageLedger
    project: str
    budget: dict[str, Any]


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
    run: Any,
    channel: str,
    budget: dict[str, Any],
) -> Environment:
    """Connect a run row to geomind: store, workspace, callbacks and budget.

    The recorder comes first, so the row is current before the event is published.
    """
    bridge = LoopBridge(asyncio.get_running_loop(), resources.factory)
    recorder = RunRecorder(resources.factory, run.id)
    studies = StudyRecorder(resources.factory, run.id, run.chat_id, run.project_id)
    publisher = EventPublisher(
        resources.redis,
        channel,
        run.id,
        settings.ASSISTANT_DELTA_TTL_SECONDS,
    )
    return Environment(
        store=DatabaseRunStore(bridge, run.id, run.chat_id),
        workspace=DatabaseWorkspace(
            bridge, BlobStore(resources.minio, settings.MINIO_BUCKET_NAME)
        ),
        callbacks=[recorder, studies, publisher],
        is_cancelled=lambda: resources.jobs.is_cancel_requested(str(run.id)),
        ledger=DatabaseUsageLedger(bridge),
        project=str(run.project_id),
        budget=budget,
    )


def build_llm(resumed: bool) -> Any:
    if settings.ASSISTANT_LLM == "fake":
        return scripted_llm(resumed)
    return gd.providers.OpenRouter(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )


def build_budget(environment: Environment) -> list[Any]:
    """Return the project budget hook; a project without a cap has none."""
    caps = {key: cap for key, cap in environment.budget.items() if cap is not None}
    if not caps:
        return []
    return [
        gd.hooks.ProjectBudget(environment.ledger, environment.project, **caps),
    ]


def build_hooks(environment: Environment) -> list[Any]:
    return [
        gd.hooks.TokenBudget(settings.ASSISTANT_RUN_MAX_TOKENS),
        *build_budget(environment),
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


def seed_problem(environment: Environment, chat_id: UUID, project_id: UUID) -> None:
    """Give a chat without a state the project's case, when that case is complete.

    The analyst agent has no ``set_case``, so a chat that started empty could never
    read or change the case the project already has.
    """
    store = environment.store
    if store.load_state(str(chat_id)) is not None:
        return
    found = environment.workspace.case(str(project_id))
    if found is None:
        return
    content, files = found
    if gemini_case.build(copy.deepcopy(content), files) is None:
        return
    for name, data in files.items():
        store.save_chat_artifact(str(chat_id), f"{CASE_ARTIFACT}{name}", data)
    store.save_state(str(chat_id), {"version": 1, "case": content})


async def start(
    environment: Environment,
    run_id: UUID,
    chat_id: UUID,
    project_id: UUID,
    message: str,
) -> Outcome:
    """Start a run under the id the backend gave it; geomind chooses loop and agent."""
    history = await asyncio.to_thread(environment.store.load_history, str(chat_id))
    await asyncio.to_thread(seed_problem, environment, chat_id, project_id)
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
