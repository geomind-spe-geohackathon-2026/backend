from src.api.v1.workspace.overview import schemas
from src.core.clients.postgres.models.activity import Activity
from src.core.clients.postgres.models.chat import Chat
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.chat import ChatRepository
from src.core.clients.postgres.repositories.progress import ProgressRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.pagination.page import PageRequest
from src.core.progress.states import build_progress

CHAT_LIMIT = 5
ACTIVITY_LIMIT = 10
ACTIVE_RUN_LIMIT = 20


def describe_chat(chat: Chat, last_run: Run | None) -> schemas.Chat:
    return schemas.Chat(
        id=chat.id,
        project=chat.project_id,
        title=chat.title,
        created=chat.created,
        last_run=schemas.ChatRun(id=last_run.id, status=last_run.status)
        if last_run
        else None,
    )


def describe_run(run: Run) -> schemas.Run:
    return schemas.Run(
        id=run.id,
        chat=run.chat_id,
        project=run.project_id,
        status=run.status,
        loop=run.loop,
        started=run.started,
        ended=run.ended,
        usage=schemas.Usage(
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            cost=run.cost,
        ),
        request=run.request,
        error=schemas.RunError.model_validate(run.error) if run.error else None,
    )


def describe_activity(activity: Activity) -> schemas.Activity:
    link = None
    if activity.link_route:
        link = schemas.Link(route=activity.link_route, id=activity.link_id)
    return schemas.Activity(
        id=activity.id,
        time=activity.created,
        actor=schemas.Actor(kind=activity.actor_kind, name=activity.actor_name),
        text=activity.text,
        link=link,
    )


async def get_overview(
    project: Project,
    progress: ProgressRepository,
    chats: ChatRepository,
    runs: RunRepository,
    activity: ActivityRepository,
) -> schemas.Overview:
    facts = await progress.facts([project.id])
    latest_chats = await chats.latest(project.id, CHAT_LIMIT)
    last_runs = await runs.last_for_chats([chat.id for chat in latest_chats])
    active = await runs.list_page(
        project.id, PageRequest(limit=ACTIVE_RUN_LIMIT), active_only=True
    )
    return schemas.Overview(
        progress=build_progress(facts[project.id]),
        chats=[describe_chat(chat, last_runs.get(chat.id)) for chat in latest_chats],
        activity=[
            describe_activity(row)
            for row in await activity.latest(project.id, ACTIVITY_LIMIT)
        ],
        active_runs=[describe_run(run) for run in active[:ACTIVE_RUN_LIMIT]],
    )
