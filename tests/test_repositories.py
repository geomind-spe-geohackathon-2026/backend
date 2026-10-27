from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.core.clients.postgres.repositories.user import UserRepository


async def test_user_repository_creates_user() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    repository = UserRepository(session)

    user = await repository.create("user@example.com", "hashed-password")

    assert user.email == "user@example.com"
    assert user.password_hash == "hashed-password"
    session.add.assert_called_once_with(user)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(user)


async def test_user_repository_rolls_back_failed_create() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate"))
    repository = UserRepository(session)

    with pytest.raises(IntegrityError):
        await repository.create("user@example.com", "hashed-password")

    session.rollback.assert_awaited_once()
    session.refresh.assert_not_awaited()
