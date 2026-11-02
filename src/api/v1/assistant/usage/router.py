from fastapi import APIRouter
from src.api.v1.assistant.usage import schemas, services
from src.core.assistant.access import RunRepositoryDependency
from src.core.security.access import QueriedProject

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get("", response_model=schemas.Usage)
async def read_usage(
    project: QueriedProject,
    runs: RunRepositoryDependency,
) -> schemas.Usage:
    return await services.read_usage(project, runs)
