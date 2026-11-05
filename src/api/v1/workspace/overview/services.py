from src.api.v1.workspace.overview import schemas
from src.core.assistant.schemas import Run, to_chat
from src.core.clients.postgres.models.activity import Activity
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.chat import ChatRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.pagination.page import PageRequest
from src.core.progress.reader import ProgressReader
from src.core.progress.states import build_progress

CHAT_LIMIT = 5
ACTIVITY_LIMIT = 10
ACTIVE_RUN_LIMIT = 20


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
    progress: ProgressReader,
    chats: ChatRepository,
    runs: RunRepository,
    activity: ActivityRepository,
) -> schemas.Overview:
    facts = await progress.facts([project.id])
    economics = await progress.economics([project.id])
    latest_chats = await chats.latest(project.id, CHAT_LIMIT)
    last_runs = await runs.last_for_chats([chat.id for chat in latest_chats])
    active = await runs.list_page(
        project.id, PageRequest(limit=ACTIVE_RUN_LIMIT), active_only=True
    )
    return schemas.Overview(
        progress=build_progress(facts[project.id], economics[project.id]),
        chats=[to_chat(chat, last_runs.get(chat.id)) for chat in latest_chats],
        activity=[
            describe_activity(row)
            for row in await activity.latest(project.id, ACTIVITY_LIMIT)
        ],
        active_runs=[Run.model_validate(run) for run in active[:ACTIVE_RUN_LIMIT]],
    )
