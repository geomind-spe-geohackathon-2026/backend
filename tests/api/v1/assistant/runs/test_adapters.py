import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import geomind as gd
import pytest

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge, LoopBridgeError
from src.api.v1.assistant.runs.adapters.store import DatabaseRunStore
from src.api.v1.assistant.runs.adapters.workspace import DatabaseWorkspace
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.plant_version import PlantVersionRepository
from tests.plants import example_plant


class Translated:
    """Present geomind's conformance names to a store that keys by UUID."""

    def __init__(self, store: DatabaseRunStore, names: dict[str, str]) -> None:
        self.store = store
        self.names = names

    def __getattr__(self, method: str):
        function = getattr(self.store, method)

        def call(first, *rest):
            return function(self.names.get(first, first), *rest)

        return call


async def seed(session_factory, owner, make_project, make_chat, make_run):
    chat = await make_chat(await make_project(owner), owner)
    first = await make_run(chat, owner)
    second = await make_run(chat, owner)
    bridge = LoopBridge(asyncio.get_running_loop(), session_factory)
    return chat, first, second, bridge


async def test_store_passes_geomind_conformance(
    session_factory, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    chat, first, second, bridge = await seed(
        session_factory, owner, make_project, make_chat, make_run
    )
    empty = await make_chat(await make_project(owner), owner)
    names = {
        "conformance-run": first.id.hex,
        "conformance-other-run": second.id.hex,
        "conformance-chat": str(empty.id),
        "conformance-missing": str(uuid4()),
    }

    def seed_history(store, chat_id, messages) -> None:
        async def add(session, chat_uuid):
            repository = MessageRepository(session)
            for message in messages:
                await repository.add(chat_uuid, message.role, message.content, None)

        store.store.bridge.call(add, UUID(names[chat_id]))

    def factory() -> Translated:
        return Translated(DatabaseRunStore(bridge, uuid4(), chat.id), names)

    def check() -> None:
        gd.testing.check_run_store(factory, seed_history)

    await asyncio.to_thread(check)


async def test_chat_artifacts_are_read_by_the_next_run_of_the_chat(
    session_factory, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    chat, first, second, bridge = await seed(
        session_factory, owner, make_project, make_chat, make_run
    )
    writer = DatabaseRunStore(bridge, first.id, chat.id)
    reader = DatabaseRunStore(bridge, second.id, chat.id)

    def check() -> None:
        writer.save_artifact(first.id.hex, "case/demand.csv", b"1,2")
        writer.save_chat_artifact(str(chat.id), "design/a", {"v": 1})
        writer.save_chat_artifact(str(chat.id), "design/a", {"v": 2})
        assert reader.load_chat_artifact(str(chat.id), "design/a") == {"v": 2}
        assert reader.load_chat_artifact(str(chat.id), "case/demand.csv") == b"1,2"
        assert reader.load_artifact(second.id.hex, "case/demand.csv") is None
        assert reader.load_chat_artifact(str(uuid4()), "design/a") is None

    await asyncio.to_thread(check)


async def test_history_leaves_out_the_message_of_the_run_itself(
    session_factory, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    chat, first, second, bridge = await seed(
        session_factory, owner, make_project, make_chat, make_run
    )
    store = DatabaseRunStore(bridge, second.id, chat.id)

    history = await asyncio.to_thread(store.load_history, str(chat.id))

    assert [message.content for message in history] == ["Size the plant"]


async def test_store_refuses_to_block_its_own_loop(
    session_factory, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    chat, first, _, bridge = await seed(
        session_factory, owner, make_project, make_chat, make_run
    )

    with pytest.raises(LoopBridgeError):
        DatabaseRunStore(bridge, first.id, chat.id).load_state(str(chat.id))


class FakeObject:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        return None

    def release_conn(self) -> None:
        return None


class FakeMinio:
    def get_object(self, bucket: str, key: str) -> FakeObject:
        return FakeObject(f"bytes of {key}".encode())


async def test_workspace_gives_plant_and_case_with_files(
    session_factory, session, make_user, make_project, tmp_path: Path
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    versions = PlantVersionRepository(session)
    await versions.save_version(project.id, example_plant(), "first", owner.id)
    case = await CaseVersionRepository(session).save_version(
        project.id, {"time": {}}, "first", owner.id
    )
    await CaseFileRepository(session).add(
        project.id, case.id, "demand.csv", 3, "objects/demand"
    )
    bridge = LoopBridge(asyncio.get_running_loop(), session_factory)
    workspace = DatabaseWorkspace(bridge, FakeMinio(), tmp_path)

    def read() -> tuple:
        return (
            workspace.plant(str(project.id)),
            workspace.case(str(project.id)),
            workspace.plant(str(uuid4())),
            workspace.case(str(uuid4())),
            workspace.documents(str(project.id), "anything"),
        )

    plant, found, no_plant, no_case, documents = await asyncio.to_thread(read)

    content, folder = found
    assert plant.to_dict() == example_plant()
    assert content == {"time": {}}
    assert (folder / "demand.csv").read_text() == "bytes of objects/demand"
    assert no_plant is None
    assert no_case is None
    assert documents == []
