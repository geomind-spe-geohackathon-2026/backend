"""The Alembic migrations build the models' schema, both ways, on an empty database."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.postgres

ROOT = Path(__file__).resolve().parent.parent


def alembic(url: str, *arguments: str) -> None:
    environment = {**os.environ, "POSTGRES_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
    )


async def empty_database(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


def test_migrations_upgrade_downgrade_and_match_the_models() -> None:
    url = os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("POSTGRES_TEST_URL is not set")
    asyncio.run(empty_database(url))

    alembic(url, "upgrade", "head")
    alembic(url, "downgrade", "base")
    alembic(url, "upgrade", "head")
    alembic(url, "check")
