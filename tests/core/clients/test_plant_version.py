from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
    content_digest,
)
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.errors import ConflictError
from src.core.gemini.plant import dump_plant, example_plant, load_plant


def changed_plant(stages: int) -> dict:
    plant = load_plant(example_plant())
    plant.update_params(**{"esp.no_stages": stages})
    return dump_plant(plant)


@pytest.fixture
async def owner(make_user):
    return await make_user()


@pytest.fixture
async def project(owner, make_project):
    return await make_project(owner)


@pytest.fixture
def repository(session) -> PlantVersionRepository:
    return PlantVersionRepository(session)


def test_digest_ignores_key_order() -> None:
    assert content_digest({"a": 1, "b": 2}) == content_digest({"b": 2, "a": 1})


async def test_save_fills_every_column(repository, project, owner) -> None:
    content = example_plant()

    version = await repository.save_version(project.id, content, "First", owner.id)

    assert version.number == 1
    assert version.plant_type == content["plant_type"]
    assert version.digest == content_digest(content)
    assert version.note == "First"
    assert version.author_id == owner.id
    assert version.created.tzinfo is not None


async def test_stored_version_round_trips_unchanged(
    repository,
    project,
    owner,
    session_factory,
) -> None:
    content = changed_plant(12)
    await repository.save_version(project.id, content, "Design", owner.id)

    async with session_factory() as other_session:
        stored = await PlantVersionRepository(other_session).latest_version(project.id)

    assert stored.content == content
    assert dump_plant(load_plant(stored.content)) == content


async def test_numbers_rise_per_project(
    repository,
    project,
    owner,
    make_project,
) -> None:
    other = await make_project(owner, "Other")

    await repository.save_version(project.id, changed_plant(1), "", owner.id)
    second = await repository.save_version(project.id, changed_plant(2), "", owner.id)
    first = await repository.save_version(other.id, changed_plant(1), "", owner.id)

    assert (second.number, first.number) == (2, 1)
    latest = await repository.latest_version(project.id)
    assert latest.number == 2


async def test_identical_content_is_a_conflict(repository, project, owner) -> None:
    await repository.save_version(project.id, example_plant(), "", owner.id)

    with pytest.raises(ConflictError):
        await repository.save_version(project.id, example_plant(), "", owner.id)


async def test_version_by_number(repository, project, owner) -> None:
    await repository.save_version(project.id, changed_plant(1), "One", owner.id)
    await repository.save_version(project.id, changed_plant(2), "Two", owner.id)

    version = await repository.version_by_number(project.id, 1)

    assert version.note == "One"
    assert await repository.version_by_number(project.id, 3) is None


async def test_list_versions_leaves_out_content(
    repository,
    project,
    owner,
    session_factory,
) -> None:
    await repository.save_version(project.id, changed_plant(1), "One", owner.id)
    await repository.save_version(project.id, changed_plant(2), "Two", owner.id)

    async with session_factory() as other_session:
        versions = await PlantVersionRepository(other_session).list_versions(project.id)

        assert [version.number for version in versions] == [1, 2]
        with pytest.raises(InvalidRequestError, match="content"):
            versions[0].content  # noqa: B018


async def test_save_retries_once_after_losing_a_number(
    repository,
    project,
    owner,
    monkeypatch,
) -> None:
    await repository.save_version(project.id, changed_plant(1), "", owner.id)
    real_latest = repository.latest_version
    stale_reads = [None]

    async def latest_after_race(project_id):
        return stale_reads.pop() if stale_reads else await real_latest(project_id)

    monkeypatch.setattr(repository, "latest_version", latest_after_race)

    version = await repository.save_version(
        project.id,
        changed_plant(2),
        "",
        owner.id,
    )

    assert version.number == 2


async def test_save_gives_up_after_the_second_loss(
    repository,
    project,
    owner,
    monkeypatch,
) -> None:
    async def always_taken(*_args):
        raise IntegrityError("insert", {}, Exception("duplicate"))

    monkeypatch.setattr(repository, "_insert_next", always_taken)

    with pytest.raises(ConflictError):
        await repository.save_version(project.id, example_plant(), "", owner.id)


async def test_saving_updates_the_project(
    repository,
    project,
    owner,
    session_factory,
) -> None:
    await repository.save_version(project.id, example_plant(), "", owner.id)

    async with session_factory() as other_session:
        stored = await ProjectRepository(other_session).get_by_id(project.id)

    assert stored.updated > project.updated
    assert stored.plant_version == 1


async def test_deleting_a_project_deletes_its_versions(
    repository,
    project,
    owner,
) -> None:
    await repository.save_version(project.id, example_plant(), "", owner.id)

    await ProjectRepository(repository.session).delete(project.id)

    assert await repository.latest_version(project.id) is None


async def test_unknown_project_is_refused(repository, owner) -> None:
    with pytest.raises(ConflictError):
        await repository.save_version(uuid4(), example_plant(), "", owner.id)
