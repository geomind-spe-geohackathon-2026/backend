from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.project import (
    ProjectRepository,
    get_project_repository,
)
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.errors import ForbiddenError
from src.core.security.errors import ProjectNotFoundError, UnauthorizedError

ProjectRepositoryDependency = Annotated[
    ProjectRepository,
    Depends(get_project_repository),
]
UserRepositoryDependency = Annotated[UserRepository, Depends(get_user_repository)]


async def current_user(
    request: Request,
    repository: UserRepositoryDependency,
) -> User:
    """Return the signed-in user, refusing tokens of deactivated users."""
    user = await repository.get_by_id(request.state.user_id)
    if user is None or not user.active:
        raise UnauthorizedError("User is inactive")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise ForbiddenError("Administrator role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def require_project(
    project_id: UUID,
    user: User,
    repository: ProjectRepository,
) -> Project:
    """Return a project its owner or an admin may use.

    Anyone else gets the same answer as for a missing project, so ids cannot be
    probed.
    """
    project = await repository.get_by_id(project_id)
    if project is None or (project.owner_id != user.id and user.role != "admin"):
        raise ProjectNotFoundError("Project not found")
    return project


async def project_from_path(
    project_id: UUID,
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
) -> Project:
    return await require_project(project_id, user, repository)


AccessibleProject = Annotated[Project, Depends(project_from_path)]
