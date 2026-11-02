from typing import Annotated

from fastapi import APIRouter, Depends
from src.api.v1.workspace.overview import schemas, services
from src.core.clients.postgres.repositories.activity import (
    ActivityRepository,
    get_activity_repository,
)
from src.core.clients.postgres.repositories.chat import (
    ChatRepository,
    get_chat_repository,
)
from src.core.clients.postgres.repositories.progress import (
    ProgressRepository,
    get_progress_repository,
)
from src.core.clients.postgres.repositories.project import (
    ProjectRepository,
    get_project_repository,
)
from src.core.clients.postgres.repositories.run import (
    RunRepository,
    get_run_repository,
)
from src.core.security.access import QueriedProject

router = APIRouter(prefix="/overview", tags=["Overview"])

ActivityRepositoryDependency = Annotated[
    ActivityRepository,
    Depends(get_activity_repository),
]
ChatRepositoryDependency = Annotated[ChatRepository, Depends(get_chat_repository)]
ProgressRepositoryDependency = Annotated[
    ProgressRepository,
    Depends(get_progress_repository),
]
ProjectRepositoryDependency = Annotated[
    ProjectRepository,
    Depends(get_project_repository),
]
RunRepositoryDependency = Annotated[RunRepository, Depends(get_run_repository)]


@router.get("", response_model=schemas.Overview)
async def get_overview(
    project: QueriedProject,
    progress: ProgressRepositoryDependency,
    chats: ChatRepositoryDependency,
    runs: RunRepositoryDependency,
    activity: ActivityRepositoryDependency,
) -> schemas.Overview:
    return await services.get_overview(project, progress, chats, runs, activity)
