import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import fakeredis
import geomind as gd
import pytest

from src.api.v1.assistant.runs.adapters.bridge import LoopBridge, LoopBridgeError
from src.api.v1.assistant.runs.adapters.callbacks import EventPublisher, StudyRecorder
from src.api.v1.assistant.runs.adapters.errors import AdapterFailedError
from src.api.v1.assistant.runs.adapters.replay import known_events
from src.api.v1.assistant.runs.adapters.session import (
    Environment,
    allowed_model_prefixes,
    build_budget,
    build_llm,
    build_sandbox,
    check_models,
    refused_models,
    seed_problem,
)
from src.api.v1.assistant.runs.adapters.store import (
    DatabaseRunStore,
    DatabaseUsageLedger,
)
from src.api.v1.assistant.runs.adapters.workspace import DatabaseWorkspace
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.mcp_server import McpServerRepository
from src.core.clients.postgres.repositories.memory import MemoryRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.plant_version import PlantVersionRepository
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.clients.postgres.repositories.run_artifact import RunArtifactRepository
from src.core.secrets import seal
from src.core.settings import settings
from tests import design_inputs
from tests.cases import DEMAND_CSV, DEMAND_FILE, example_case
from tests.conftest import bearer
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

    assert [message.content for message in history] == ["Save a demand profile"]


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
    documents = RagDocumentRepository(session)
    text = "Brine salinity is high"
    document = await documents.create(project.id, "notes.txt", len(text), "k", owner.id)
    await documents.set_text(document, text)
    blobs.objects["k"] = text.encode()


async def test_workspace_gives_the_newest_upload_of_each_name(
    session_factory, session, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    documents = RagDocumentRepository(session)
    await documents.create(project.id, "demand.csv", 3, "old", owner.id)
    await documents.create(project.id, "demand.csv", 5, "new", owner.id)
    await documents.create(project.id, "notes.bin9", 1, "other", owner.id)
    blobs.objects["new"] = b"a,b\n1"
    workspace = DatabaseWorkspace(
        LoopBridge(asyncio.get_running_loop(), session_factory), blobs
    )
    project_id = str(project.id)

    listed = await asyncio.to_thread(workspace.files, project_id)
    read = await asyncio.to_thread(workspace.file, project_id, "demand.csv")
    missing = await asyncio.to_thread(workspace.file, project_id, "nothing.csv")

    assert listed == [
        {"name": "demand.csv", "size": 5, "media_type": "text/csv"},
        {
            "name": "notes.bin9",
            "size": 1,
            "media_type": "application/octet-stream",
        },
    ]
    assert read == b"a,b\n1"
    assert missing is None


async def test_the_loop_reads_warmed_plants_and_files_without_blocking(
    session_factory, session, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await seed_workspace(session, owner, project, blobs)
    workspace = DatabaseWorkspace(
        LoopBridge(asyncio.get_running_loop(), session_factory), blobs
    )
    project_id = str(project.id)
    with pytest.raises(LoopBridgeError):
        workspace.files(project_id)

    await workspace.warm(project_id)

    assert [item["name"] for item in workspace.files(project_id)] == ["notes.txt"]
    assert workspace.file(project_id, "notes.txt") == b"Brine salinity is high"
    assert list(workspace.plants(project_id)) == list(
        await asyncio.to_thread(workspace.plants, project_id)
    )


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


def recorded_event() -> dict[str, Any]:
    return {
        "type": "study.recorded",
        "sequence": 4,
        "run_id": "a" * 32,
        "agent": "designer",
        "parent": None,
        "time": "2026-11-02T00:00:00Z",
        "run": "a" * 32,
        "index": 1,
        "study": "study/first",
        "tool": "run_study",
        "method": "minimize",
        "designs": ["plant"],
    }


def test_a_stored_event_of_an_unknown_type_is_skipped() -> None:
    assert known_events([{"type": "from.a.newer.version", "sequence": 1}]) == []


def test_a_known_event_is_kept_next_to_an_unknown_one() -> None:
    events = known_events([{"type": "unknown"}, recorded_event()])

    assert [event.type for event in events] == ["study.recorded"]


async def test_studies_index_is_rewritten_in_the_chat(
    session_factory, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    chat, first, _, bridge = await seed(
        session_factory, owner, make_project, make_chat, make_run
    )
    store = DatabaseRunStore(bridge, first.id, chat.id)

    def rewrite() -> Any:
        store.save_chat_artifact(str(chat.id), "studies.index", [{"study": "a"}])
        store.save_chat_artifact(str(chat.id), "studies.index", [{"study": "b"}])
        return store.load_chat_artifact(str(chat.id), "studies.index")

    assert await asyncio.to_thread(rewrite) == [{"study": "b"}]


async def test_a_recorded_study_joins_the_study_list(
    client, session_factory, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    run = await make_run(chat, owner)
    recorder = StudyRecorder(session_factory, run.id, chat.id, project.id)
    async with session_factory() as session:
        await RunArtifactRepository(session).save(
            None, chat.id, "study/first", {"study": {"method": "minimize"}}
        )

    await recorder.on_event(None, gd.event_from_dict(recorded_event()))

    response = await client.get(
        "/api/v1/design/study",
        params={"project": str(project.id)},
        headers=bearer(owner),
    )
    study = response.json()["items"][0]
    assert (study["name"], study["kind"]) == ("first", "minimize")
    assert study["status"] == "done"
    assert study["settings"] == {"method": "minimize"}
    assert study["started_by"]["kind"] == "agent"
    assert study["started_by"]["run"] == str(run.id)


async def test_the_ledger_counts_every_other_run_a_waiting_one_too(
    session_factory, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    spent = {"input_tokens": 10, "output_tokens": 5, "cost": 0.5}
    await make_run(chat, owner, status="done", values=spent)
    await make_run(chat, owner, status="failed", values=spent)
    await make_run(chat, owner, status="waiting", values=spent)
    current = await make_run(chat, owner, status="running", values=spent)
    bridge = LoopBridge(asyncio.get_running_loop(), session_factory)
    ledger = DatabaseUsageLedger(bridge, current.id)

    usage = await asyncio.to_thread(ledger.spent, str(project.id))

    assert (usage.input_tokens, usage.output_tokens) == (30, 15)
    assert usage.cost == 1.5


def environment_with(budget: dict[str, Any]) -> Environment:
    return Environment(None, None, [], lambda: False, None, "project", budget)


def test_a_project_without_caps_has_no_budget_hook() -> None:
    assert build_budget(environment_with({"max_tokens": None, "max_cost": None})) == []


def test_a_project_with_a_cap_has_a_budget_hook() -> None:
    hooks = build_budget(environment_with({"max_tokens": None, "max_cost": 2.0}))

    assert isinstance(hooks[0], gd.hooks.ProjectBudget)
    assert hooks[0].max_cost == 2.0


class SeedStore:
    def __init__(self, state: Any = None) -> None:
        self.state = state
        self.artifacts: dict[str, bytes] = {}

    def load_state(self, _chat: str) -> Any:
        return self.state

    def save_state(self, _chat: str, state: dict[str, Any]) -> None:
        self.state = state

    def save_chat_artifact(self, _chat: str, key: str, data: bytes) -> None:
        self.artifacts[key] = data


class SeedWorkspace:
    def __init__(self, found: Any) -> None:
        self.found = found

    def case(self, _project: str) -> Any:
        return self.found


def seeded(store: SeedStore, found: Any) -> SeedStore:
    environment = Environment(
        store, SeedWorkspace(found), [], lambda: False, None, "project", {}
    )
    seed_problem(environment, uuid4(), uuid4())
    return store


def test_a_new_chat_starts_with_the_complete_case_of_the_project() -> None:
    content, files = design_inputs.case_content(), design_inputs.case_files()

    store = seeded(SeedStore(), (content, files))

    assert store.state == {"version": 1, "case": content}
    assert set(store.artifacts) == {f"case/{name}" for name in files}


def test_a_chat_with_a_case_keeps_it() -> None:
    state = {"version": 3, "case": {"name": "own"}}
    found = (design_inputs.case_content(), design_inputs.case_files())

    assert seeded(SeedStore(state), found).state == state


def test_a_chat_with_a_state_but_no_case_takes_the_project_case() -> None:
    content, files = design_inputs.case_content(), design_inputs.case_files()

    state = seeded(SeedStore({"version": 3, "goal": "x"}), (content, files)).state

    assert state == {"version": 4, "goal": "x", "case": content}


def test_a_project_without_a_case_leaves_the_chat_empty() -> None:
    assert seeded(SeedStore(), None).state is None


def test_an_incomplete_case_is_not_given_to_the_chat() -> None:
    content = design_inputs.case_content()
    del content["site"]["reservoir"]["thickness"]["value"]

    assert seeded(SeedStore(), (content, design_inputs.case_files())).state is None


async def test_a_warmed_chat_artifact_is_read_on_the_loop(
    session_factory, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    chat, first, _, bridge = await seed(
        session_factory, owner, make_project, make_chat, make_run
    )
    store = DatabaseRunStore(bridge, first.id, chat.id)
    await asyncio.to_thread(store.save_chat_artifact, str(chat.id), "case/a.csv", b"x")
    fresh = DatabaseRunStore(bridge, first.id, chat.id)

    await fresh.warm_chat(str(chat.id))

    assert fresh.load_chat_artifact(str(chat.id), "case/a.csv") == b"x"


async def test_the_ledger_answers_on_the_loop_once_warmed(
    session_factory, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    spent = {"input_tokens": 10, "output_tokens": 5, "cost": 0.5}
    await make_run(chat, owner, status="done", values=spent)
    ledger = DatabaseUsageLedger(
        LoopBridge(asyncio.get_running_loop(), session_factory)
    )

    await ledger.warm(str(project.id))

    assert ledger.spent(str(project.id)).input_tokens == 10


async def test_a_file_the_assistant_wrote_can_be_read_from_the_chat(
    client, session_factory, make_user, make_project, make_chat
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    async with session_factory() as session:
        await RunArtifactRepository(session).save(
            None, chat.id, "case/data/a.csv", b"time,a"
        )

    found = await client.get(
        f"/api/v1/assistant/chat/{chat.id}/files/data/a.csv", headers=bearer(owner)
    )
    missing = await client.get(
        f"/api/v1/assistant/chat/{chat.id}/files/data/b.csv", headers=bearer(owner)
    )

    assert found.content == b"time,a"
    assert missing.status_code == 404


def test_a_model_outside_the_allowed_family_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("GEOMIND_MODEL", "anthropic/claude-sonnet-5.5")
    monkeypatch.setenv("GEOMIND_CHEAP_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    monkeypatch.setattr(settings, "ASSISTANT_LLM", "openrouter")

    with pytest.raises(AdapterFailedError, match="claude-sonnet"):
        build_llm(False, "hello")


def test_an_unset_model_stops_the_app_with_the_setting_to_add(monkeypatch) -> None:
    monkeypatch.delenv("GEOMIND_MODEL", raising=False)
    monkeypatch.delenv("GEOMIND_CHEAP_MODEL", raising=False)
    monkeypatch.setattr(settings, "ASSISTANT_LLM", "openrouter")

    with pytest.raises(AdapterFailedError, match="GEOMIND_CHEAP_MODEL"):
        check_models()


def test_unset_retries_stop_the_app_with_the_setting_to_add(monkeypatch) -> None:
    monkeypatch.setenv("GEOMIND_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    monkeypatch.setenv("GEOMIND_CHEAP_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    monkeypatch.delenv("GEOMIND_RETRY_COUNT", raising=False)
    monkeypatch.setattr(settings, "ASSISTANT_LLM", "openrouter")

    with pytest.raises(AdapterFailedError, match="GEOMIND_RETRY_COUNT"):
        check_models()


def test_the_scripted_assistant_needs_no_model(monkeypatch) -> None:
    monkeypatch.delenv("GEOMIND_MODEL", raising=False)
    monkeypatch.setattr(settings, "ASSISTANT_LLM", "fake")

    check_models()


@pytest.mark.parametrize("name", [".env.example", ".env.dev.example"])
def test_env_examples_name_only_allowed_models(name: str) -> None:
    lines = Path(name).read_text(encoding="utf-8").splitlines()
    models = dict(line.split("=", 1) for line in lines if "_MODEL=" in line)

    assert set(models) >= {"GEOMIND_MODEL", "GEOMIND_CHEAP_MODEL"}
    assert all(value.startswith(allowed_model_prefixes()) for value in models.values())


def test_several_model_prefixes_may_be_allowed(monkeypatch) -> None:
    nemotron = "nvidia/nemotron-3.5-super-vl:free"
    monkeypatch.setattr(
        settings, "ASSISTANT_MODEL_PREFIX", "deepseek/, nvidia/nemotron-"
    )
    monkeypatch.setenv("GEOMIND_MODEL", nemotron)
    monkeypatch.setenv("GEOMIND_CHEAP_MODEL", "deepseek/deepseek-v4.1-flash-1017")

    assert refused_models() == []


def test_a_model_outside_every_prefix_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ASSISTANT_MODEL_PREFIX", "nvidia/nemotron-")
    monkeypatch.setenv("GEOMIND_MODEL", "nvidia/nemotron-3.5-super-vl:free")
    monkeypatch.setenv("GEOMIND_CHEAP_MODEL", "deepseek/deepseek-v4.1-flash-1017")

    assert refused_models() == ["deepseek/deepseek-v4.1-flash-1017"]


def test_deepseek_everywhere_is_allowed(monkeypatch) -> None:
    monkeypatch.setenv("GEOMIND_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    monkeypatch.setenv("GEOMIND_CHEAP_MODEL", "deepseek/deepseek-v4.1-flash-1017")

    assert refused_models() == []


async def test_the_live_stream_gives_a_failed_tool_its_problem() -> None:
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    publisher = EventPublisher(redis, "channel", uuid4(), 60)
    subscriber = redis.pubsub()
    await subscriber.subscribe("channel")
    await subscriber.get_message(timeout=1)
    problem = {"code": "no_case", "path": None, "message": "No case", "suggestions": []}
    recorded = SimpleNamespace(
        type="tool.result",
        is_public=False,
        is_error=True,
        agent="designer",
        call_id="c1",
        output={"error": problem},
    )
    finished = SimpleNamespace(
        type="tool.finished",
        is_public=True,
        agent="designer",
        call_id="c1",
        sequence=4,
        data=lambda: {"call_id": "c1", "error": "cut"},
    )

    await publisher.on_event(None, recorded)
    await publisher.on_event(None, finished)

    message = await subscriber.get_message(ignore_subscribe_messages=True, timeout=1)
    assert json.loads(message["data"])["data"]["problem"] == problem
    await subscriber.aclose()
    await redis.aclose()


async def test_memory_is_given_only_to_a_project_that_chose_it(
    session_factory, session, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    on = await make_project(owner, "On")
    undecided = await make_project(owner, "Undecided")
    projects = ProjectRepository(session)
    await projects.set_choices(await projects.get_by_id(on.id), "on", None)
    lesson = {"id": "lesson-1", "origin": "curator", "project_id": None}
    await MemoryRepository(session).put("experience", lesson, None, ("agent", "r0"))
    bridge = LoopBridge(asyncio.get_running_loop(), session_factory)
    workspace = DatabaseWorkspace(bridge, blobs, "run-1")

    memory = await asyncio.to_thread(workspace.memory, str(on.id))
    nothing = await asyncio.to_thread(workspace.memory, str(undecided.id))
    seen = await asyncio.to_thread(memory.entries, "experience")
    design = {"id": "design-1", "origin": "code", "project_id": str(on.id)}
    await asyncio.to_thread(memory.add, "experience", design)

    assert nothing is None
    assert seen == [lesson]
    stored = await MemoryRepository(session).get("experience", "design-1")
    assert stored.data == design
    assert stored.project_id is None
    assert (stored.created_by_kind, stored.created_by) == ("agent", "run-1")


async def test_the_loop_reads_warmed_memory_and_connectors(
    session_factory, session, make_user, make_project, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    connector = await McpServerRepository(session).create(
        {
            "name": "wells",
            "url": "https://mcp.example.com",
            "transport": "http",
            "auth": "header",
            "header_name": "X-Key",
            "secret": seal("k"),
        }
    )
    off = await McpServerRepository(session).create(
        {
            "name": "off",
            "url": "https://off.example.com",
            "transport": "http",
            "auth": "none",
            "enabled": False,
        }
    )
    projects = ProjectRepository(session)
    await projects.set_choices(
        await projects.get_by_id(project.id), "on", [connector.id, off.id]
    )
    workspace = DatabaseWorkspace(
        LoopBridge(asyncio.get_running_loop(), session_factory), blobs
    )
    project_id = str(project.id)

    await workspace.warm(project_id)

    assert workspace.connectors(project_id) == [
        {
            "name": "wells",
            "url": "https://mcp.example.com",
            "transport": "http",
            "headers": {"X-Key": "k"},
        }
    ]
    assert workspace.memory(project_id).entries("experience") == []


async def test_the_shared_knowledge_is_searched_by_passage_with_its_page(
    session_factory, session, make_user, blobs
) -> None:
    owner = await make_user()
    documents = RagDocumentRepository(session)
    text = (
        "[page 1]\nIntroduction to wells.\n[page 2]\nThe drilling cost is 1500 EUR/m."
    )
    shared = await documents.create(None, "costs.pdf", 10, "k/costs.pdf", owner.id)
    await documents.set_text(shared, text)
    blobs.objects["k/costs.pdf"] = b"%PDF"
    workspace = DatabaseWorkspace(
        LoopBridge(asyncio.get_running_loop(), session_factory), blobs
    )

    hits = await asyncio.to_thread(workspace.knowledge_search, "drilling cost")
    files = await asyncio.to_thread(workspace.knowledge_files)
    data = await asyncio.to_thread(workspace.knowledge_file, "costs.pdf")
    nothing = await asyncio.to_thread(workspace.knowledge_file, "other.pdf")

    assert hits[0]["document"] == "costs.pdf" and hits[0]["page"] == 2
    assert "1500 EUR/m" in hits[0]["text"]
    assert set(hits[0]) == {"id", "document", "title", "page", "text", "score"}
    assert [item["name"] for item in files] == ["costs.pdf"]
    assert (data, nothing) == (b"%PDF", None)


def test_a_geomind_without_a_sandbox_gets_no_sandbox_argument(monkeypatch) -> None:
    monkeypatch.delattr(gd, "sandbox", raising=False)
    assert build_sandbox() == {}


def test_a_geomind_with_a_sandbox_gets_one_or_none(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ASSISTANT_SANDBOX", "none")
    if getattr(gd, "sandbox", None) is not None:
        assert build_sandbox() == {"sandbox": None}
