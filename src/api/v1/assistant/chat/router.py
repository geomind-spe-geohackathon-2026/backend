from typing import Annotated

from fastapi import APIRouter, Depends, status
from src.api.v1.assistant.chat import schemas, services
from src.core.assistant.access import (
    AccessibleChat,
    ChatRepositoryDependency,
    ProjectRepositoryDependency,
    RunRepositoryDependency,
)
from src.core.assistant.queue import EnqueueDependency
from src.core.assistant.schemas import Chat
from src.core.clients.postgres.repositories.chat_state import (
    ChatStateRepository,
    get_chat_state_repository,
)
from src.core.clients.postgres.repositories.message import (
    MessageRepository,
    get_message_repository,
)
from src.core.pagination.page import Page, PageParams
from src.core.security.access import CurrentUser, QueriedProject, require_project

router = APIRouter(prefix="/chat", tags=["Chat"])

MessageRepositoryDependency = Annotated[
    MessageRepository,
    Depends(get_message_repository),
]
ChatStateRepositoryDependency = Annotated[
    ChatStateRepository,
    Depends(get_chat_state_repository),
]


@router.get("", response_model=Page[Chat])
async def list_chats(
    project: QueriedProject,
    page: PageParams,
    chats: ChatRepositoryDependency,
    runs: RunRepositoryDependency,
) -> Page:
    return await services.list_chats(project, page, chats, runs)


@router.post(
    "",
    response_model=Chat,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat(
    payload: schemas.ChatCreate,
    user: CurrentUser,
    projects: ProjectRepositoryDependency,
    chats: ChatRepositoryDependency,
) -> Chat:
    project = await require_project(payload.project, user, projects)
    return await services.create_chat(payload, project, user, chats)


@router.get("/{chat_id}/messages", response_model=Page[schemas.Message])
async def list_messages(
    chat: AccessibleChat,
    page: PageParams,
    messages: MessageRepositoryDependency,
) -> Page:
    return await services.list_messages(chat, page, messages)


@router.post(
    "/{chat_id}/messages",
    response_model=schemas.MessageSent,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    payload: schemas.MessageCreate,
    chat: AccessibleChat,
    user: CurrentUser,
    chats: ChatRepositoryDependency,
    runs: RunRepositoryDependency,
    messages: MessageRepositoryDependency,
    enqueue: EnqueueDependency,
) -> schemas.MessageSent:
    return await services.send_message(
        chat, payload, user, chats, runs, messages, enqueue
    )


@router.patch("/{chat_id}", response_model=Chat)
async def rename_chat(
    payload: schemas.ChatUpdate,
    chat: AccessibleChat,
    chats: ChatRepositoryDependency,
    runs: RunRepositoryDependency,
) -> Chat:
    return await services.rename_chat(chat, payload, chats, runs)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat: AccessibleChat,
    chats: ChatRepositoryDependency,
    runs: RunRepositoryDependency,
) -> None:
    await services.delete_chat(chat, chats, runs)


@router.get("/{chat_id}/state", response_model=schemas.ChatState)
async def read_state(
    chat: AccessibleChat,
    states: ChatStateRepositoryDependency,
) -> schemas.ChatState:
    return await services.read_state(chat, states)
