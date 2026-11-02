from typing import Annotated
from uuid import UUID

from fastapi import Depends
from src.core.clients.postgres.models.project import Project
from src.core.security.access import (
    CurrentUser,
    ProjectRepositoryDependency,
    require_project,
)


async def project_from_query(
    project: UUID,
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
) -> Project:
    """Return the project named by ``?project=`` if the caller may use it."""
    return await require_project(project, user, repository)


QueriedProject = Annotated[Project, Depends(project_from_query)]
