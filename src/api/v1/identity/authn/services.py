from sqlalchemy.exc import IntegrityError

from src.api.v1.identity.authn import schemas
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.clients.redis.models.revoked_access_token import RevokedAccessToken
from src.core.clients.redis.repositories.revoked_access_token import (
    RevokedAccessTokenRepository,
)
from src.core.errors import ConflictError, ForbiddenError
from src.core.logging.logger import get_logger
from src.core.security.errors import UnauthorizedError
from src.core.security.jwt import AccessTokenClaims, create_access_token
from src.core.security.passwords import (
    hash_password,
    verify_dummy_password,
    verify_password,
)

logger = get_logger(__name__)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def token_response(user: User) -> schemas.TokenResponse:
    return schemas.TokenResponse(
        access_token=create_access_token(user.id),
        user=schemas.UserResponse.model_validate(user),
    )


async def signup_user(
    credentials: schemas.Credentials,
    repository: UserRepository,
) -> schemas.TokenResponse:
    email = normalize_email(credentials.email)
    existing_user = await repository.get_by_email(email)
    if existing_user is not None:
        raise ConflictError("Email is already registered")

    try:
        user = await repository.create(email, hash_password(credentials.password))
    except IntegrityError as exc:
        raise ConflictError("Email is already registered") from exc
    return token_response(user)


async def signin_user(
    credentials: schemas.Credentials,
    repository: UserRepository,
) -> schemas.TokenResponse:
    email = normalize_email(credentials.email)
    user = await repository.get_by_email(email)
    if user is None:
        verify_dummy_password(credentials.password)
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise ForbiddenError("User is inactive")
    return token_response(user)


async def signout_user(
    claims: AccessTokenClaims,
    repository: RevokedAccessTokenRepository,
) -> None:
    await repository.revoke(
        RevokedAccessToken(
            token_id=claims.token_id,
            expires_at=claims.expires_at,
        )
    )


async def request_password_reset(
    payload: schemas.ForgotPasswordRequest,
    repository: UserRepository,
) -> schemas.MessageResponse:
    email = normalize_email(payload.email)
    user = await repository.get_by_email(email)
    if user is not None:
        logger.info("Password reset requested for user %s", user.id)
    return schemas.MessageResponse(
        message="If the account exists, password reset instructions will be sent"
    )
