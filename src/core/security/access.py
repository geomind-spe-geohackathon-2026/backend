from typing import Annotated

from fastapi import Depends, Request
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.errors import ForbiddenError
from src.core.security.errors import UnauthorizedError

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
