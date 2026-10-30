import asyncio
import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.clients.postgres.client import Base
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.gemini.plant import dump_plant, example_plant, load_plant

pytestmark = pytest.mark.postgres


@pytest.fixture
async def postgres() -> AsyncIterator[AsyncEngine]:
    url = os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("POSTGRES_TEST_URL is not set")
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def factory(postgres: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(postgres, expire_on_commit=False, autoflush=False)


@pytest.fixture
async def project(factory):
    async with factory() as session:
        user = await UserRepository(session).create("user@example.com", "hash", "User")
        return await ProjectRepository(session).create("Doublet", user.id)


def changed_plant(stages: int) -> dict:
    plant = load_plant(example_plant())
    plant.update_params(**{"esp.no_stages": stages})
    return dump_plant(plant)


async def test_jsonb_round_trips_a_version_unchanged(factory, project) -> None:
    content = changed_plant(12)
    async with factory() as session:
        await PlantVersionRepository(session).save_version(
            project.id,
            content,
            "",
            project.owner_id,
        )

    async with factory() as session:
        stored = await PlantVersionRepository(session).latest_version(project.id)

    assert stored.content == content


async def test_concurrent_saves_get_different_numbers(factory, project) -> None:
    async def save(stages: int) -> int:
        async with factory() as session:
            version = await PlantVersionRepository(session).save_version(
                project.id,
                changed_plant(stages),
                "",
                project.owner_id,
            )
            return version.number

    numbers = await asyncio.gather(save(1), save(2))

    assert sorted(numbers) == [1, 2]


async def test_deleting_a_project_cascades(factory, project) -> None:
    async with factory() as session:
        repository = PlantVersionRepository(session)
        await repository.save_version(
            project.id,
            example_plant(),
            "",
            project.owner_id,
        )
        await ProjectRepository(session).delete(project.id)

        assert await repository.latest_version(project.id) is None
