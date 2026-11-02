import asyncio
from uuid import UUID, uuid4

import geomind as gd
import pytest

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge, LoopBridgeError
from src.api.v1.assistant.runs.adapters.store import DatabaseRunStore
from src.api.v1.assistant.runs.adapters.workspace import DatabaseWorkspace
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.document import DocumentRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.plant_version import PlantVersionRepository
from tests.cases import DEMAND_CSV, DEMAND_FILE, example_case
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
        "conformance-other-chat": str(uuid4()),
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
        writer.save_chat_artifact(str(chat.id), "case/demand.csv", b"1,2")
        writer.save_artifact(first.id.hex, "only-run", b"1")
        writer.save_chat_artifact(str(chat.id), "design/a", {"v": 1})
        writer.save_chat_artifact(str(chat.id), "design/a", {"v": 2})
        assert reader.load_chat_artifact(str(chat.id), "design/a") == {"v": 2}
        assert reader.load_chat_artifact(str(chat.id), "case/demand.csv") == b"1,2"
        assert reader.load_artifact(second.id.hex, "case/demand.csv") is None
        assert reader.load_chat_artifact(str(chat.id), "only-run") is None
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


async def seed_workspace(session, owner, project, blobs) -> None:
    await PlantVersionRepository(session).save_version(
        project.id, example_plant(), "first", owner.id
    )
    case = await CaseVersionRepository(session).save_version(
        project.id, example_case(), "first", owner.id
    )
    key = f"{project.id}/demand"
    blobs.objects[key] = DEMAND_CSV
    await CaseFileRepository(session).add(
        project.id, case.id, DEMAND_FILE, len(DEMAND_CSV), key
    )
    documents = DocumentRepository(session)
    text = "Brine salinity is high"
    document = await documents.create(project.id, "notes.txt", len(text), "k", owner.id)
    await documents.set_text(document, text)


async def test_workspace_passes_geomind_conformance(
    session_factory, session, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await seed_workspace(session, owner, project, blobs)
    bridge = LoopBridge(asyncio.get_running_loop(), session_factory)

    def check() -> None:
        gd.testing.check_workspace(
            lambda: DatabaseWorkspace(bridge, blobs),
            project=str(project.id),
            query="salinity",
            missing_project=str(uuid4()),
        )

    await asyncio.to_thread(check)


async def test_workspace_names_the_plant_after_its_document(
    session_factory, session, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await seed_workspace(session, owner, project, blobs)
    bridge = LoopBridge(asyncio.get_running_loop(), session_factory)
    workspace = DatabaseWorkspace(bridge, blobs)

    plants = await asyncio.to_thread(workspace.plants, str(project.id))
    found = await asyncio.to_thread(workspace.case, str(project.id))

    assert plants == {example_plant()["name"]: example_plant()}
    assert found == (example_case(), {DEMAND_FILE: DEMAND_CSV})
