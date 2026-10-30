from typing import Annotated

from fastapi import APIRouter, Depends, status
from src.api.v1.identity.me import schemas, services
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.security.access import CurrentUser
from src.core.security.schemas import UserResponse

router = APIRouter(prefix="/me", tags=["Me"])

UserRepositoryDependency = Annotated[UserRepository, Depends(get_user_repository)]


@router.get("", response_model=UserResponse)
async def get_me(user: CurrentUser) -> UserResponse:
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: schemas.ChangePassword,
    user: CurrentUser,
    repository: UserRepositoryDependency,
) -> None:
    await services.change_password(user, payload, repository)
