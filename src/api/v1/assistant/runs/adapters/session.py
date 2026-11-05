import asyncio
import copy
import json
import os
import re
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
from src.api.v1.assistant.runs.adapters.errors import (
    AdapterFailedError,
    AnsweredRequestError,
    StaleRequestError,
)
from src.api.v1.assistant.runs.adapters.fake import scripted_llm
from src.api.v1.assistant.runs.adapters.simulated import SimulationRecorder
from src.api.v1.assistant.runs.adapters.store import (
    DatabaseRunStore,
    DatabaseUsageLedger,
)
from src.api.v1.assistant.runs.adapters.versions import VersionRecorder
from src.core.clients.redis.repositories.chat_auto_approve import auto_approve_on
from src.api.v1.assistant.runs.adapters.workspace import DatabaseWorkspace
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.redis.repositories.job import SyncJobRepository
from src.core.gemini import case as gemini_case
from src.core.settings import settings

CASE_ARTIFACT = "case/"
MODEL_SUFFIX = "_model"


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
    auto_approve: bool = False


@dataclass(frozen=True)
class Outcome:
    """How a run ended or paused; ``answer`` is text, empty when there is none."""

    status: str
    stop_reason: str | None
    answer: str
    input_tokens: int
    output_tokens: int
    cost: float
    suggestions: list[dict[str, str]] | None = None


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

    The recorder comes first, so the row is current before the event is published;
    the version recorder saves a settled case or plant before its event goes out.
    """
    bridge = LoopBridge(asyncio.get_running_loop(), resources.factory)
    recorder = RunRecorder(resources.factory, run.id)
    blobs = BlobStore(resources.minio, settings.MINIO_BUCKET_NAME)
    versions = VersionRecorder(
        resources.factory, blobs, run.chat_id, run.project_id, run.author_id
    )
    studies = StudyRecorder(resources.factory, run.id, run.chat_id, run.project_id)
    simulations = SimulationRecorder(
        resources.factory, run.id, run.chat_id, run.project_id
    )
    publisher = EventPublisher(
        resources.redis,
        channel,
        run.id,
        settings.ASSISTANT_DELTA_TTL_SECONDS,
    )
    return Environment(
        store=DatabaseRunStore(bridge, run.id, run.chat_id),
        workspace=DatabaseWorkspace(bridge, blobs, run.id.hex),
        callbacks=[recorder, versions, studies, simulations, publisher],
        is_cancelled=lambda: resources.jobs.is_cancel_requested(str(run.id)),
        ledger=DatabaseUsageLedger(bridge, run.id),
        project=str(run.project_id),
        budget=budget,
        auto_approve=auto_approve_on(resources.jobs.redis, str(run.chat_id)),
    )


def allowed_model_prefixes() -> tuple[str, ...]:
    """Return the model id prefixes a run may use."""
    parts = settings.ASSISTANT_MODEL_PREFIX.split(",")
    return tuple(part.strip() for part in parts if part.strip())


def refused_models() -> list[str]:
    """Return the models geomind would use that the app does not allow.

    ``ASSISTANT_MODEL_PREFIX`` is one model id prefix or several, comma separated.
    """
    allowed = allowed_model_prefixes()
    return sorted(
        {
            value
            for name, value in gd.runtime.state().items()
            if name.endswith(MODEL_SUFFIX)
            and isinstance(value, str)
            and not value.startswith(allowed)
        }
    )


def memory_source() -> str:
    """Return where a run's memory comes from: the workspace's store when on."""
    return "store" if os.environ.get("GEOMIND_MEMORY") == "on" else "off"


def check_models() -> None:
    """Refuse model settings that would fail a run: unset or not allowed."""
    if settings.ASSISTANT_LLM == "fake":
        return
    refused = refused_models()
    if refused:
        raise AdapterFailedError(f"Models not allowed: {', '.join(refused)}")
    missing = gd.runtime.model_problems(memory_source())
    if missing:
        raise AdapterFailedError(f"Settings missing: {'; '.join(missing)}")


def build_llm(resumed: bool, message: str) -> Any:
    if settings.ASSISTANT_LLM == "fake":
        return scripted_llm(resumed, message)
    check_models()
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


def build_run_cap() -> list[Any]:
    """Return the run's token cap hook; ``ASSISTANT_RUN_MAX_TOKENS=off`` gives none."""
    cap = settings.ASSISTANT_RUN_MAX_TOKENS
    return [] if cap is None else [gd.hooks.TokenBudget(cap)]


def build_hooks(environment: Environment) -> list[Any]:
    return [
        *build_run_cap(),
        *build_budget(environment),
        gd.hooks.Cancellation(environment.is_cancelled),
    ]


def build_sandbox() -> dict[str, Any]:
    """Return the sandbox argument of a run, or nothing for a geomind that has none.

    geomind after 0.4.21 runs no code of its own and takes no sandbox.
    """
    if getattr(gd, "sandbox", None) is None:
        return {}
    if settings.ASSISTANT_SANDBOX == "docker":
        return {"sandbox": gd.sandbox.DockerSandbox()}
    return {"sandbox": None}


def build_permissions(auto_approve: bool = False) -> Any:
    """Ask before writes, or allow every tool when the chat's auto-approve is on (QA-031)."""
    return gd.Permissions(mode="auto" if auto_approve else "ask")


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
        suggestions=suggestions_of(result),
    )


def suggestions_of(result: Any) -> list[dict[str, str]] | None:
    """Return the next steps geomind gave with a run's answer, or ``None``."""
    found = getattr(result, "suggestions", None)
    if not found:
        return None
    return [
        {"label": str(item["label"]), "message": str(item["message"])}
        for item in found
        if isinstance(item, dict) and item.get("label") and item.get("message")
    ] or None


def keywords(
    environment: Environment, resumed: bool, message: str = ""
) -> dict[str, Any]:
    return {
        "llm": build_llm(resumed, message),
        "store": environment.store,
        "workspace": environment.workspace,
        **build_sandbox(),
        "permissions": build_permissions(environment.auto_approve),
        "callbacks": environment.callbacks,
        "hooks": build_hooks(environment),
    }


def seed_problem(environment: Environment, chat_id: UUID, project_id: UUID) -> None:
    """Give a chat whose state has no case the project's case, when that is complete.

    A chat that started empty would otherwise never read or change the case the
    project already has. A case in the state is kept: it
    may hold the assistant's own changes.
    """
    store = environment.store
    state = store.load_state(str(chat_id)) or {}
    if state.get("case") is not None:
        return
    found = environment.workspace.case(str(project_id))
    if found is None:
        return
    content, files = found
    if gemini_case.build(copy.deepcopy(content), files) is None:
        return
    for name, data in files.items():
        store.save_chat_artifact(str(chat_id), f"{CASE_ARTIFACT}{name}", data)
    version = state.get("version", 0) + 1
    store.save_state(str(chat_id), {**state, "version": version, "case": content})


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
    await environment.store.warm(run_id.hex)
    await environment.store.warm_chat(str(chat_id))
    await environment.ledger.warm(environment.project)
    await environment.workspace.warm(environment.project)
    try:
        run = gd.Run(
            message=message,
            chat=str(chat_id),
            project=str(project_id),
            history=history,
            **keywords(environment, False, message),
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
    """Answer a pending request, or with none continue a run that was cancelled.

    geomind's AlreadyAnsweredError (0.4.73) means the request was settled: the run goes on, or
    waits on another request.
    """
    try:
        await environment.store.warm(run_id.hex)
        await environment.store.warm_chat(str(environment.store.chat_id))
        await environment.ledger.warm(environment.project)
        await environment.workspace.warm(environment.project)
        run = await asyncio.to_thread(
            gd.Run.load,
            run_id.hex,
            **keywords(environment, resumed=True),
        )
        return to_outcome(await run.aresume(request_id, answer))
    except gd.errors.RequestError as error:
        answered = getattr(gd.errors, "AlreadyAnsweredError", None)
        if answered is not None and isinstance(error, answered):
            waiting = WAITS_ON.search(str(error))
            if waiting:
                raise StaleRequestError(waiting.group(1)) from error
            raise AnsweredRequestError(str(error)) from error
        found = EXPECTED_REQUEST.search(str(error))
        if found:
            raise StaleRequestError(found.group(1)) from error
        if "unknown or already answered" in str(error):
            raise AnsweredRequestError(str(error)) from error
        raise AdapterFailedError(str(error)) from error
    except gd.errors.GeomindError as error:
        raise AdapterFailedError(str(error)) from error


EXPECTED_REQUEST = re.compile(r"expected '([^']+)'")
WAITS_ON = re.compile(r"waits on '([^']+)'")
"""geomind's refusal of an answer to a request that is not the pending one (QA-056)."""


def failure_event(
    run_id: UUID, sequence: int, message: str, stop_reason: str = "error"
) -> EventRecord:
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
            "stop_reason": stop_reason,
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
