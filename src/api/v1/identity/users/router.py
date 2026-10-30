from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from src.api.v1.identity.users import schemas, services
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.pagination.page import Page, PageParams
from src.core.security.access import AdminUser
from src.core.security.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])

UserRepositoryDependency = Annotated[UserRepository, Depends(get_user_repository)]


@router.get("", response_model=Page[UserResponse])
async def list_users(
    _admin: AdminUser,
    page: PageParams,
    repository: UserRepositoryDependency,
) -> Page:
    return await services.list_users(page, repository)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: schemas.UserCreate,
    _admin: AdminUser,
    repository: UserRepositoryDependency,
) -> UserResponse:
    return await services.create_user(payload, repository)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: schemas.UserUpdate,
    admin: AdminUser,
    repository: UserRepositoryDependency,
) -> UserResponse:
    return await services.update_user(user_id, payload, admin, repository)
