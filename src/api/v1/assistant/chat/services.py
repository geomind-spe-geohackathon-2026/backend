from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from src.api.v1.assistant.chat import schemas
from src.core.assistant import schemas as shared
from src.core.assistant.errors import QueueUnavailableError
from src.core.assistant.queue import Enqueue
from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.models.chat import Chat
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.chat import ChatRepository
from src.core.clients.postgres.repositories.chat_state import ChatStateRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.run_artifact import (
    RunArtifactRepository,
)
from src.core.errors import ConflictError
from src.core.gemini.errors import CaseFileNotFoundError
from src.core.pagination.page import Page, PageRequest, build_page, encode_cursor

DEFAULT_TITLE = "New chat"
START_TASK = "assistant.runs.start"
TITLE_LENGTH = 60

CASE_ARTIFACT = "case/"


async def list_chats(
    project: Project,
    page: PageRequest,
    chats: ChatRepository,
    runs: RunRepository,
) -> Page:
    rows = await chats.list_page(project.id, page)
    items = rows[: page.limit]
    last = await runs.last_for_chats([chat.id for chat in items]) if items else {}
    has_more = len(rows) > page.limit
    cursor = encode_cursor(items[-1].created, items[-1].id) if has_more else None
    return Page(
        items=[shared.to_chat(chat, last.get(chat.id)) for chat in items],
        next=cursor,
    )


async def create_chat(
    payload: schemas.ChatCreate,
    project: Project,
    user: User,
    chats: ChatRepository,
) -> shared.Chat:
    chat = await chats.create(project.id, payload.title or DEFAULT_TITLE, user.id)
    return shared.to_chat(chat, None)


async def rename_chat(
    chat: Chat,
    payload: schemas.ChatUpdate,
    chats: ChatRepository,
    runs: RunRepository,
) -> shared.Chat:
    renamed = await chats.rename(chat, payload.title)
    last = await runs.last_for_chats([chat.id])
    return shared.to_chat(renamed, last.get(chat.id))


async def delete_chat(chat: Chat, chats: ChatRepository, runs: RunRepository) -> None:
    if await runs.has_active(chat.id):
        raise ConflictError("The chat has a run that is not finished")
    await chats.delete(chat.id)


async def list_messages(
    chat: Chat,
    page: PageRequest,
    messages: MessageRepository,
) -> Page:
    rows = await messages.list_page(chat.id, page)
    return build_page(rows, page, schemas.Message)


async def read_state(chat: Chat, states: ChatStateRepository) -> schemas.ChatState:
    latest = await states.latest(chat.id)
    if latest is None:
        return schemas.ChatState(version=0, state=None)
    return schemas.ChatState(version=latest.version, state=latest.state)


async def read_file(chat: Chat, name: str, artifacts: RunArtifactRepository) -> bytes:
    """Return a case file the assistant wrote in a chat."""
    found = await artifacts.newest_for_chat(chat.id, f"{CASE_ARTIFACT}{name}")
    if found is None or not isinstance(found.data, bytes):
        raise CaseFileNotFoundError("File not found")
    return found.data


async def queue_run(run: Run, runs: RunRepository, enqueue: Enqueue) -> None:
    """Hand a new run to the worker; if the queue is down the run is marked failed."""
    try:
        await run_in_threadpool(enqueue, START_TASK, str(run.id))
    except QueueUnavailableError as error:
        error_body = {"code": error.code, "message": error.message}
        await runs.update(
            run,
            {"status": "failed", "error": error_body, "ended": utc_now()},
        )
        raise


def title_of(content: str) -> str:
    """Return the first line of a message, shortened at a word to the title length."""
    line = " ".join(content.split())
    if len(line) <= TITLE_LENGTH:
        return line
    cut = line[: TITLE_LENGTH - 1].rsplit(" ", 1)[0]
    return cut + "\u2026"


async def send_message(
    chat: Chat,
    payload: schemas.MessageCreate,
    user: User,
    chats: ChatRepository,
    runs: RunRepository,
    messages: MessageRepository,
    enqueue: Enqueue,
) -> schemas.MessageSent:
    """Add the user's message and queue a run for it; one run at a time per chat."""
    if await runs.has_active(chat.id):
        raise ConflictError("The chat has a run that is not finished")
    run = await runs.create(uuid4(), chat.id, chat.project_id, user.id)
    message = await messages.add(chat.id, "user", payload.content, run.id)
    if chat.title == DEFAULT_TITLE:
        await chats.rename(chat, title_of(payload.content))
    await chats.touch(chat)
    await queue_run(run, runs, enqueue)
    return schemas.MessageSent(
        message=schemas.Message.model_validate(message),
        run=shared.Run.model_validate(run),
    )
