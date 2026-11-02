import logging

import pytest

from src.core.clients.postgres.repositories.user import UserRepository
from src.core.pagination.page import PageRequest
from src.core.security.bootstrap import ensure_first_admin
from src.core.security.passwords import verify_password
from src.core.settings import settings


@pytest.fixture
def first_admin(monkeypatch) -> None:
    monkeypatch.setattr(settings, "FIRST_ADMIN_EMAIL", "Root@Example.com")
    monkeypatch.setattr(settings, "FIRST_ADMIN_PASSWORD", "first-admin-password")


async def users(session_factory) -> list:
    async with session_factory() as session:
        return await UserRepository(session).list_page(PageRequest())


@pytest.mark.usefixtures("first_admin")
async def test_creates_admin_once_without_logging_secrets(
    session_factory,
    caplog,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="geomind"):
        await ensure_first_admin(session_factory)
        await ensure_first_admin(session_factory)

    created = await users(session_factory)
    assert [(user.email, user.role) for user in created] == [
        ("root@example.com", "admin")
    ]
    assert verify_password("first-admin-password", created[0].password_hash)
    assert "first-admin-password" not in caplog.text
    assert "root@example.com" not in caplog.text.lower()


@pytest.mark.usefixtures("first_admin")
async def test_keeps_existing_admin(session_factory, make_user) -> None:
    await make_user("admin@example.com", role="admin")

    await ensure_first_admin(session_factory)

    assert [user.email for user in await users(session_factory)] == [
        "admin@example.com"
    ]


async def test_does_nothing_without_settings(session_factory) -> None:
    await ensure_first_admin(session_factory)

    assert await users(session_factory) == []
