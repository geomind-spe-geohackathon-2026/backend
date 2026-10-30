from src.api.v1.identity.me import schemas
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.errors import ValidationFailedError
from src.core.security.passwords import hash_password, verify_password


async def change_password(
    user: User,
    payload: schemas.ChangePassword,
    repository: UserRepository,
) -> None:
    if not verify_password(payload.old_password, user.password_hash):
        raise ValidationFailedError({"old_password": "Password is incorrect"})
    await repository.update(
        user,
        {"password_hash": hash_password(payload.new_password)},
    )
