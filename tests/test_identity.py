from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.api.v1.identity.authn.router import forgot_password, signin, signout, signup
from src.api.v1.identity.authn.schemas import Credentials, ForgotPasswordRequest
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.clients.redis.repositories.revoked_access_token import (
    RevokedAccessTokenRepository,
)
from src.core.security.jwt import AccessTokenClaims, decode_access_token
from src.core.security.passwords import hash_password


async def test_signup_creates_user_and_token() -> None:
    repository = AsyncMock(spec=UserRepository)
    repository.get_by_email.return_value = None
    user = User(id=uuid4(), email="user@example.com", password_hash="hashed")
    repository.create.return_value = user

    response = await signup(
        Credentials(email="User@Example.com", password="correct-password"),
        repository,
    )

    email, password_hash = repository.create.call_args.args
    assert email == "user@example.com"
    assert password_hash != "correct-password"
    assert decode_access_token(response.access_token).subject == user.id


async def test_signin_returns_token_for_valid_credentials() -> None:
    user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash=hash_password("correct-password"),
        is_active=True,
    )
    repository = AsyncMock(spec=UserRepository)
    repository.get_by_email.return_value = user

    response = await signin(
        Credentials(email="user@example.com", password="correct-password"),
        repository,
    )

    assert response.user.id == user.id
    assert decode_access_token(response.access_token).subject == user.id


async def test_signout_revokes_token() -> None:
    claims = AccessTokenClaims(
        subject=uuid4(),
        token_id="token-id",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    request = SimpleNamespace(state=SimpleNamespace(access_token_claims=claims))
    repository = AsyncMock(spec=RevokedAccessTokenRepository)

    response = await signout(request, repository)

    assert response is None
    repository.revoke.assert_awaited_once()
    revoked_access_token = repository.revoke.call_args.args[0]
    assert revoked_access_token.token_id == "token-id"
    assert revoked_access_token.expires_at == claims.expires_at


async def test_forgot_password_has_generic_response() -> None:
    repository = AsyncMock(spec=UserRepository)
    repository.get_by_email.return_value = None

    response = await forgot_password(
        ForgotPasswordRequest(email="missing@example.com"),
        repository,
    )

    assert response.message == (
        "If the account exists, password reset instructions will be sent"
    )
