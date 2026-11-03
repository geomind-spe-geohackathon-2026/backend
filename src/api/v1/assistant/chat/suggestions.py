from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from src.api.v1.assistant.chat import schemas, services
from src.core.assistant.access import (
    ChatRepositoryDependency,
)
from src.core.assistant.errors import ChatNotFoundError
from src.core.clients.postgres.repositories.chat_state import (
    ChatStateRepository,
    get_chat_state_repository,
)
from src.core.security.access import CurrentUser, QueriedProject

router = APIRouter(prefix="/suggestions", tags=["Chat"])

ChatStateRepositoryDependency = Annotated[
    ChatStateRepository, Depends(get_chat_state_repository)
]


@router.get("", response_model=schemas.Suggestions)
async def suggest(
    project: QueriedProject,
    _user: CurrentUser,
    chats: ChatRepositoryDependency,
    states: ChatStateRepositoryDependency,
    chat: Annotated[UUID | None, Query()] = None,
) -> schemas.Suggestions:
    """Next steps for a new chat of a project, or for one of its chats."""
    found = None
    if chat is not None:
        found = await chats.get_by_id(chat)
        if found is None or found.project_id != project.id:
            raise ChatNotFoundError("Chat not found")
    return await services.suggest(project, found, states)
