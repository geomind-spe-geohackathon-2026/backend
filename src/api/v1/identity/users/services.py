from uuid import UUID

from sqlalchemy.exc import IntegrityError

from src.api.v1.identity.users import schemas
from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.errors import ConflictError, NotFoundError
from src.core.pagination.page import Page, PageRequest, build_page
from src.core.security.emails import normalize_email
from src.core.security.passwords import hash_password
from src.core.security.schemas import UserResponse


class UserNotFoundError(NotFoundError):
    code = "user_not_found"


async def list_users(page: PageRequest, repository: UserRepository) -> Page:
    rows = await repository.list_page(page)
    return build_page(rows, page, UserResponse, created="created_at")


async def create_user(
    payload: schemas.UserCreate,
    repository: UserRepository,
) -> User:
    try:
        return await repository.create(
            normalize_email(payload.email),
            hash_password(payload.password),
            name=payload.name,
            role=payload.role,
        )
    except IntegrityError as exc:
        raise ConflictError("Email is already registered") from exc


async def update_user(
    user_id: UUID,
    payload: schemas.UserUpdate,
    admin: User,
    repository: UserRepository,
) -> User:
    user = await repository.get_by_id(user_id)
    if user is None:
        raise UserNotFoundError("User not found")

    values = payload.model_dump(exclude_none=True)
    if user.id == admin.id and (
        values.get("active") is False or values.get("role", "admin") != "admin"
    ):
        raise ConflictError("Administrators cannot remove their own access")
    if values.get("active") is False:
        values["tokens_valid_after"] = utc_now()
    return await repository.update(user, values)
