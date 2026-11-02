from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.v1.design.study import tasks
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.jobs import control
from tests import design_inputs
from tests.blobs import MemoryBlobStore, blobs  # noqa: F401


@pytest.fixture(autouse=True)
def use_memory_blobs(blobs: MemoryBlobStore) -> None:  # noqa: F811
    return None


@pytest.fixture
def queued(monkeypatch: pytest.MonkeyPatch) -> list[UUID]:
    ids: list[UUID] = []

    def enqueue(study_id: UUID) -> str:
        ids.append(study_id)
        return f"task-{len(ids)}"

    monkeypatch.setattr(tasks, "enqueue", enqueue)
    return ids


@pytest.fixture
def terminated(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    found: list[str] = []
    monkeypatch.setattr(control, "terminate", found.append)
    return found


@pytest.fixture
def save_inputs(
    session_factory: async_sessionmaker[AsyncSession],
    blobs: MemoryBlobStore,  # noqa: F811
) -> Callable[[Project, User], Awaitable[None]]:
    async def save(project: Project, owner: User, files: bool = True) -> None:
        async with session_factory() as session:
            plant = PlantVersionRepository(session)
            await plant.save_version(
                project.id, design_inputs.plant_content(), "p", owner.id
            )
            case = await CaseVersionRepository(session).save_version(
                project.id, design_inputs.case_content(), "c", owner.id
            )
            if not files:
                return
            for name, data in design_inputs.case_files().items():
                blobs.objects[f"{project.id}/{name}"] = data
                await CaseFileRepository(session).add(
                    project.id, case.id, name, len(data), f"{project.id}/{name}"
                )

    return save


def study_body(project: Project, **changes: Any) -> dict[str, Any]:
    body = {"project": str(project.id), "kind": "run", "name": "Base", "settings": {}}
    return {**body, **changes}


@pytest.fixture
def killed_later(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    found: list[str] = []
    monkeypatch.setattr(control, "terminate_later", found.append)
    return found
