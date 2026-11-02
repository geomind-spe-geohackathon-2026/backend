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
from src.fastapi import app
from tests import design_inputs


class Body:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        return None

    def release_conn(self) -> None:
        return None


class FakeMinio:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def get_object(self, bucket: str, key: str) -> Body:
        return Body(self.objects[key])


@pytest.fixture(autouse=True)
def minio() -> FakeMinio:
    fake = FakeMinio()
    app.state.minio = fake
    yield fake
    app.state.minio = None


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
    minio: FakeMinio,
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
                minio.objects[f"{project.id}/{name}"] = data
                await CaseFileRepository(session).add(
                    project.id, case.id, name, len(data), f"{project.id}/{name}"
                )

    return save


def study_body(project: Project, **changes: Any) -> dict[str, Any]:
    body = {"project": str(project.id), "kind": "run", "name": "Base", "settings": {}}
    return {**body, **changes}
