from collections.abc import AsyncIterable
from typing import Annotated, Literal
from uuid import UUID

from fastapi.sse import EventSourceResponse, ServerSentEvent

from fastapi import APIRouter, Depends, Query, Response, WebSocket
from src.api.v1.assistant.runs import schemas, services, socket
from src.core.assistant import schemas as shared
from src.core.assistant.access import (
    AccessibleRun,
    RunRepositoryDependency,
    SessionFactory,
)
from src.core.assistant.queue import EnqueueDependency
from src.core.clients.postgres.repositories.base import DatabaseSession
from src.core.clients.postgres.repositories.run_event import (
    RunEventRepository,
    get_run_event_repository,
)
from src.core.clients.redis.client import RedisClient
from src.core.clients.redis.repositories.job import JobRepository, get_job_repository
from src.core.pagination.page import Page, PageParams
from src.core.security.access import QueriedProject
from src.core.sse.follow import last_event_id

router = APIRouter(prefix="/runs", tags=["Runs"])

RunEventRepositoryDependency = Annotated[
    RunEventRepository,
    Depends(get_run_event_repository),
]
JobRepositoryDependency = Annotated[JobRepository, Depends(get_job_repository)]


@router.get("", response_model=Page[shared.Run])
async def list_runs(
    project: QueriedProject,
    page: PageParams,
    runs: RunRepositoryDependency,
    run_status: Annotated[Literal["active"] | None, Query(alias="status")] = None,
) -> Page:
    return await services.list_runs(project, page, run_status, runs)


@router.get("/{run_id}", response_model=shared.Run)
async def get_run(
    run: AccessibleRun, events: RunEventRepositoryDependency
) -> shared.Run:
    return await services.read_run(run, events)


@router.get("/{run_id}/events", response_class=EventSourceResponse)
async def stream_events(
    run: AccessibleRun,
    redis: RedisClient,
    factory: SessionFactory,
    session: DatabaseSession,
    after: Annotated[int, Depends(last_event_id)],
) -> AsyncIterable[ServerSentEvent]:
    run_id = run.id
    await session.close()
    async for item in services.follow_run(run_id, redis, factory, after):
        yield item


@router.websocket("/{run_id}/stream")
async def stream_socket(websocket: WebSocket, run_id: UUID) -> None:
    await socket.serve_run(websocket, run_id)


@router.get("/{run_id}/log")
async def get_log(run: AccessibleRun, events: RunEventRepositoryDependency) -> dict:
    return await services.read_log(run, events)


@router.get("/{run_id}/agents", response_model=schemas.RunAgents)
async def get_agents(
    run: AccessibleRun, events: RunEventRepositoryDependency
) -> schemas.RunAgents:
    return await services.read_agents(run, events)


@router.get(
    "/{run_id}/log/export",
    response_class=Response,
    responses={200: {"content": {"application/json": {}, "text/markdown": {}}}},
)
async def export_log(
    run: AccessibleRun,
    events: RunEventRepositoryDependency,
    export_format: Annotated[Literal["json", "md"], Query(alias="format")],
) -> Response:
    text, media_type, filename = await services.export_log(run, export_format, events)
    return Response(
        content=text,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{run_id}/answer", response_model=shared.Run)
async def answer_run(
    body: schemas.RunAnswer,
    run: AccessibleRun,
    runs: RunRepositoryDependency,
    enqueue: EnqueueDependency,
) -> shared.Run:
    return shared.Run.model_validate(
        await services.answer_run(run, body, runs, enqueue)
    )


@router.post("/{run_id}/cancel", response_model=shared.Run)
async def cancel_run(
    run: AccessibleRun,
    runs: RunRepositoryDependency,
    jobs: JobRepositoryDependency,
    enqueue: EnqueueDependency,
) -> shared.Run:
    return shared.Run.model_validate(
        await services.cancel_run(run, runs, jobs, enqueue)
    )
