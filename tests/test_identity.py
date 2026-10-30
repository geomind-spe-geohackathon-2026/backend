from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.api.v1.identity.authn.router import login, logout
from src.api.v1.identity.authn.schemas import Credentials
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.clients.redis.repositories.revoked_access_token import (
    RevokedAccessTokenRepository,
)
from src.core.security.jwt import AccessTokenClaims, decode_access_token
from src.core.security.passwords import hash_password


async def test_login_returns_token_for_valid_credentials() -> None:
    user = User(
        id=uuid4(),
        email="user@example.com",
        name="user",
        role="member",
        password_hash=hash_password("correct-password"),
        active=True,
    )
    repository = AsyncMock(spec=UserRepository)
    repository.get_by_email.return_value = user

    response = await login(
        Credentials(email="user@example.com", password="correct-password"),
        repository,
    )

    assert response.user.id == user.id
    assert decode_access_token(response.access_token).subject == user.id


async def test_logout_revokes_token() -> None:
    claims = AccessTokenClaims(
        subject=uuid4(),
        token_id="token-id",
        refresh_token_id="refresh-id",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    request = SimpleNamespace(state=SimpleNamespace(access_token_claims=claims))
    repository = AsyncMock(spec=RevokedAccessTokenRepository)

    response = await logout(request, object(), repository)

    assert response is None
    access, refresh = (call.args[0] for call in repository.revoke.await_args_list)
    assert access.token_id == "token-id"
    assert access.expires_at == claims.expires_at
    assert refresh.token_id == "refresh-id"
