import tarfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.clients.postgres.client import Base
from src.core.clients.postgres.models.activity import Activity
from src.core.clients.postgres.models.case_file import CaseFile
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.chat import Chat
from src.core.clients.postgres.models.chat_state import ChatState
from src.core.clients.postgres.models.document import Document
from src.core.clients.postgres.models.memory_entry import MemoryEntry
from src.core.clients.postgres.models.message import Message
from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.result import Result
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.models.run_artifact import RunArtifact
from src.core.clients.postgres.models.run_event import RunEvent
from src.core.clients.postgres.models.study import Study
from src.core.clients.postgres.models.user import User
from src.scripts import projects

WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


class MemoryBlobs:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def keys(self, prefix: str) -> list[str]:
        return [key for key in self.objects if key.startswith(prefix)]


def full_project(owner: User) -> list[object]:
    """Return one project with a row in every table that belongs to a project."""
    project = Project(id=uuid4(), name="Site", owner_id=owner.id, budget_max_cost=2.5)
    version = CaseVersion(
        id=uuid4(),
        project_id=project.id,
        number=1,
        content={"a": 1},
        missing=0,
        digest="d",
        note="n",
        author_id=owner.id,
        created=WHEN,
    )
    chat = Chat(id=uuid4(), project_id=project.id, title="T", author_id=owner.id)
    run = Run(
        id=uuid4(),
        chat_id=chat.id,
        project_id=project.id,
        author_id=owner.id,
        status="done",
        cost=0.25,
    )
    study = Study(
        id=uuid4(),
        project_id=project.id,
        kind="run",
        name="S",
        settings={},
        status="done",
        started_by_kind="agent",
        started_by_name="designer",
        started_by_run_id=run.id,
    )
    return [
        project,
        version,
        CaseFile(
            id=uuid4(),
            project_id=project.id,
            case_version_id=version.id,
            name="f.csv",
            size=1,
            object_key=f"case/{project.id}/abc",
        ),
        PlantVersion(
            id=uuid4(),
            project_id=project.id,
            number=1,
            content={"b": 2},
            digest="d",
            note="n",
            author_id=owner.id,
        ),
        chat,
        ChatState(id=uuid4(), chat_id=chat.id, version=1, state={"c": 3}),
        run,
        Message(id=uuid4(), chat_id=chat.id, role="user", content="M", run_id=run.id),
        RunEvent(
            id=uuid4(),
            run_id=run.id,
            sequence=1,
            type="usage",
            public=True,
            data={"cost": 0.25},
        ),
        RunArtifact(
            id=uuid4(),
            chat_id=chat.id,
            key="k",
            kind="bytes",
            data_bytes=b"\x00\xff",
        ),
        study,
        Result(
            id=uuid4(),
            project_id=project.id,
            study_id=study.id,
            name="R",
            summary={},
            content={"d": 4},
        ),
        Document(
            id=uuid4(),
            project_id=project.id,
            name="n.txt",
            size=1,
            object_key=f"projects/{project.id}/documents/1/n.txt",
            searchable="ready",
            author_id=owner.id,
        ),
        Activity(
            id=uuid4(),
            project_id=project.id,
            actor_kind="user",
            actor_name="A",
            text="T",
        ),
        MemoryEntry(
            id=uuid4(),
            section="experience",
            entry_id=f"fact-{project.id}",
            data={"id": f"fact-{project.id}", "origin": "code"},
            project_id=project.id,
            created_by_kind="agent",
            created_by=None,
        ),
    ]


async def add_all(engine: AsyncEngine, rows: list[object]) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        for row in rows:
            session.add(row)
            await session.flush()
        await session.commit()


def a_user(email: str) -> User:
    return User(
        id=uuid4(),
        email=email,
        name=email,
        password_hash="hash",
    )


async def counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as connection:
        return {
            table.name: await connection.scalar(select(func.count()).select_from(table))
            for table in projects.project_tables()
        }


async def all_rows(engine: AsyncEngine, table: str) -> list[dict[str, object]]:
    async with engine.connect() as connection:
        found = await connection.execute(select(Base.metadata.tables[table]))
        return [dict(row) for row in found.mappings()]


@pytest.fixture
async def target() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        engine.sync_engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def filled(engine: AsyncEngine) -> tuple[Project, MemoryBlobs]:
    owner = a_user("old@example.test")
    rows = full_project(owner)
    other = full_project(owner)
    await add_all(engine, [owner, *rows, *other])
    project = rows[0]
    assert isinstance(project, Project)
    blobs = MemoryBlobs()
    blobs.objects[f"case/{project.id}/abc"] = b"case bytes"
    blobs.objects[f"projects/{project.id}/documents/1/n.txt"] = b"doc bytes"
    blobs.objects[f"plant/{project.id}/layout.json"] = b"{}"
    blobs.objects[f"plant/{uuid4()}/layout.json"] = b"another project"
    return project, blobs


async def export_to(
    engine: AsyncEngine, blobs: MemoryBlobs, ids: list[UUID], path: Path
) -> dict[str, object]:
    async with engine.begin() as connection:
        return await projects.export_bundle(connection, blobs, ids, path)


async def import_from(
    engine: AsyncEngine, blobs: MemoryBlobs, path: Path, email: str
) -> dict[str, object]:
    async with engine.begin() as connection:
        return await projects.import_bundle(connection, blobs, path, email)


def test_every_table_has_a_rule() -> None:
    for table in projects.project_tables():
        assert projects.rows_of_table(table, [uuid4()]) is not None


async def test_a_round_trip_keeps_rows_and_objects(
    engine: AsyncEngine,
    target: AsyncEngine,
    filled: tuple[Project, MemoryBlobs],
    tmp_path: Path,
) -> None:
    project, blobs = filled
    path = tmp_path / "bundle.tar"
    new_owner = a_user("new@example.test")
    await add_all(target, [new_owner])
    arrived = MemoryBlobs()

    manifest = await export_to(engine, blobs, [project.id], path)
    await import_from(target, arrived, path, new_owner.email)

    assert await counts(target) == manifest["counts"]
    assert set(manifest["counts"].values()) == {1}
    assert arrived.objects == {
        f"case/{project.id}/abc": b"case bytes",
        f"projects/{project.id}/documents/1/n.txt": b"doc bytes",
        f"plant/{project.id}/layout.json": b"{}",
    }
    assert (await all_rows(target, "projects"))[0]["id"] == project.id
    assert (await all_rows(target, "projects"))[0]["owner_id"] == new_owner.id
    assert (await all_rows(target, "projects"))[0]["budget_max_cost"] == 2.5
    assert (await all_rows(target, "case_versions"))[0]["author_id"] == new_owner.id
    assert (await all_rows(target, "case_versions"))[0]["created"] == WHEN
    assert (await all_rows(target, "run_artifacts"))[0]["data_bytes"] == b"\x00\xff"
    assert (await all_rows(target, "run_artifacts"))[0]["data_json"] is None
    assert (await all_rows(target, "runs"))[0]["cost"] == 0.25


async def test_import_refuses_ids_that_exist_and_writes_nothing(
    engine: AsyncEngine,
    target: AsyncEngine,
    filled: tuple[Project, MemoryBlobs],
    tmp_path: Path,
) -> None:
    project, blobs = filled
    path = tmp_path / "bundle.tar"
    new_owner = a_user("new@example.test")
    await add_all(target, [new_owner])
    arrived = MemoryBlobs()
    await export_to(engine, blobs, [project.id], path)
    await import_from(target, arrived, path, new_owner.email)
    before = await counts(target)

    with pytest.raises(projects.TransferError, match="already in the database"):
        await import_from(target, MemoryBlobs(), path, new_owner.email)

    assert await counts(target) == before


async def test_import_needs_an_existing_owner(
    engine: AsyncEngine,
    target: AsyncEngine,
    filled: tuple[Project, MemoryBlobs],
    tmp_path: Path,
) -> None:
    project, blobs = filled
    path = tmp_path / "bundle.tar"
    await export_to(engine, blobs, [project.id], path)

    with pytest.raises(projects.TransferError, match="No user"):
        await import_from(target, MemoryBlobs(), path, "nobody@example.test")

    assert set((await counts(target)).values()) == {0}


async def test_export_refuses_an_unknown_project(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    with pytest.raises(projects.TransferError, match="No such project"):
        await export_to(engine, MemoryBlobs(), [uuid4()], tmp_path / "b.tar")


async def test_a_missing_object_is_listed_not_hidden(
    engine: AsyncEngine, filled: tuple[Project, MemoryBlobs], tmp_path: Path
) -> None:
    project, blobs = filled
    del blobs.objects[f"case/{project.id}/abc"]
    path = tmp_path / "bundle.tar"

    manifest = await export_to(engine, blobs, [project.id], path)

    assert manifest["missing_objects"] == [f"case/{project.id}/abc"]
    with tarfile.open(path) as bundle:
        assert f"objects/case/{project.id}/abc" not in bundle.getnames()
