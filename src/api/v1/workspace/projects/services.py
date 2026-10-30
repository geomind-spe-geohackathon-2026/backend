from src.api.v1.workspace.projects import schemas
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.pagination.page import Page, PageRequest, build_page


async def list_projects(
    user: User,
    page: PageRequest,
    repository: ProjectRepository,
) -> Page:
    owner_id = None if user.role == "admin" else user.id
    rows = await repository.list_page(page, owner_id)
    return build_page(rows, page, schemas.ProjectResponse)


async def create_project(
    payload: schemas.ProjectCreate,
    user: User,
    repository: ProjectRepository,
) -> Project:
    return await repository.create(payload.name, user.id)


async def delete_project(project: Project, repository: ProjectRepository) -> None:
    await repository.delete(project.id)
