from datetime import UTC, datetime, timedelta

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
from src.core.security.emails import normalize_email
from src.core.security.errors import TokenValidationError, UnauthorizedError
from src.core.security.jwt import (
    AccessTokenClaims,
    create_token_pair,
    decode_refresh_token,
)
from src.core.security.passwords import (
    hash_password,
    verify_dummy_password,
    verify_password,
)
from src.core.settings import settings

logger = get_logger(__name__)


def token_response(user: User) -> schemas.TokenResponse:
    tokens = create_token_pair(user.id)
    return schemas.TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=user,
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
        user = await repository.create(
            email,
            hash_password(credentials.password),
            name=email.partition("@")[0],
        )
    except IntegrityError as exc:
        raise ConflictError("Email is already registered") from exc
    return token_response(user)


async def login_user(
    credentials: schemas.Credentials,
    repository: UserRepository,
) -> schemas.TokenResponse:
    email = normalize_email(credentials.email)
    user = await repository.get_by_email(email)
    if user is None:
        verify_dummy_password(credentials.password)
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if not user.active:
        raise ForbiddenError("User is inactive")
    return token_response(user)


async def refresh_tokens(
    payload: schemas.RefreshRequest,
    users: UserRepository,
    revoked_tokens: RevokedAccessTokenRepository,
) -> schemas.TokenPairResponse:
    """Swap a refresh token for a new pair; each refresh token works once."""
    try:
        claims = decode_refresh_token(payload.refresh_token)
    except TokenValidationError:
        raise UnauthorizedError("Invalid or expired token") from None

    user = await users.get_by_id(claims.subject)
    if user is None or not user.active:
        raise UnauthorizedError("User is inactive")
    unused = await revoked_tokens.revoke(
        RevokedAccessToken(claims.token_id, claims.expires_at)
    )
    if not unused:
        raise UnauthorizedError("Token has been revoked")
    tokens = create_token_pair(user.id)
    return schemas.TokenPairResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


async def logout_user(
    claims: AccessTokenClaims,
    repository: RevokedAccessTokenRepository,
) -> None:
    await repository.revoke(RevokedAccessToken(claims.token_id, claims.expires_at))
    refresh_expiry = datetime.now(UTC) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    await repository.revoke(RevokedAccessToken(claims.refresh_token_id, refresh_expiry))


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
