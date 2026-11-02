from typing import Annotated
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fastapi import Depends, Request
from src.core.assistant.errors import ChatNotFoundError, RunNotFoundError
from src.core.clients.errors import ClientNotInitializedError
from src.core.clients.postgres.models.chat import Chat
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.repositories.chat import (
    ChatRepository,
    get_chat_repository,
)
from src.core.clients.postgres.repositories.project import (
    ProjectRepository,
    get_project_repository,
)
from src.core.clients.postgres.repositories.run import (
    RunRepository,
    get_run_repository,
)
from src.core.security.access import CurrentUser, require_project
from src.core.security.errors import ProjectNotFoundError

ChatRepositoryDependency = Annotated[ChatRepository, Depends(get_chat_repository)]
ProjectRepositoryDependency = Annotated[
    ProjectRepository,
    Depends(get_project_repository),
]
RunRepositoryDependency = Annotated[RunRepository, Depends(get_run_repository)]


async def chat_from_path(
    chat_id: UUID,
    user: CurrentUser,
    chats: ChatRepositoryDependency,
    projects: ProjectRepositoryDependency,
) -> Chat:
    """Return a chat of a project the user may use; others see ``chat_not_found``."""
    chat = await chats.get_by_id(chat_id)
    if chat is None:
        raise ChatNotFoundError("Chat not found")
    try:
        await require_project(chat.project_id, user, projects)
    except ProjectNotFoundError as error:
        raise ChatNotFoundError("Chat not found") from error
    return chat


async def run_from_path(
    run_id: UUID,
    user: CurrentUser,
    runs: RunRepositoryDependency,
    projects: ProjectRepositoryDependency,
) -> Run:
    """Return a run of a project the user may use; others see ``run_not_found``."""
    run = await runs.get_by_id(run_id)
    if run is None:
        raise RunNotFoundError("Run not found")
    try:
        await require_project(run.project_id, user, projects)
    except ProjectNotFoundError as error:
        raise RunNotFoundError("Run not found") from error
    return run


AccessibleChat = Annotated[Chat, Depends(chat_from_path)]
AccessibleRun = Annotated[Run, Depends(run_from_path)]


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "postgres_session_factory", None)
    if factory is None:
        raise ClientNotInitializedError("PostgreSQL is not initialized")
    return factory


SessionFactory = Annotated[
    async_sessionmaker[AsyncSession],
    Depends(get_session_factory),
]
