from typing import Any

import gemini as gm
import geomind as gd

from src.api.v1.assistant.runs.adapters.versions import VersionRecorder
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.plant_version import PlantVersionRepository
from src.core.clients.postgres.repositories.run_artifact import RunArtifactRepository
from tests.cases import DEMAND_CSV, DEMAND_FILE, broken_case, example_case
from tests.conftest import bearer
from tests.plants import example_plant

BASE = {
    "sequence": 7,
    "run_id": "a" * 32,
    "agent": "case_lead",
    "parent": "b" * 32,
    "time": "2026-11-04T00:00:00Z",
}


def case_set(content: dict[str, Any]) -> Any:
    changes = [{"op": "replace", "path": "/case", "value": content}]
    return gd.event_from_dict(
        {**BASE, "type": "state.changed", "version": 2, "changes": changes}
    )


def plant_built(
    name: str,
    is_error: bool = False,
    tool: str = "build_plant",
    given: dict[str, Any] | None = None,
) -> Any:
    return gd.event_from_dict(
        {
            **BASE,
            "type": "tool.result",
            "index": 3,
            "call_id": "c1",
            "tool": tool,
            "input": {"name": name, "plant": {}} if given is None else given,
            "output": {"design": f"design/{name}"},
            "is_error": is_error,
        }
    )


async def recorder_for(session_factory, blobs, make_user, make_project, make_chat):
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    recorder = VersionRecorder(session_factory, blobs, chat.id, project.id, owner.id)
    return owner, project, chat, recorder


async def save_artifact(session_factory, chat_id, key: str, data: Any) -> None:
    async with session_factory() as session:
        await RunArtifactRepository(session).save(None, chat_id, key, data)


async def test_an_accepted_case_becomes_the_project_case_with_its_files(
    client, session_factory, session, blobs, make_user, make_project, make_chat
) -> None:
    owner, project, chat, recorder = await recorder_for(
        session_factory, blobs, make_user, make_project, make_chat
    )
    await save_artifact(session_factory, chat.id, f"case/{DEMAND_FILE}", DEMAND_CSV)

    await recorder.on_event(None, case_set(example_case()))
    await recorder.on_event(None, case_set(example_case()))

    response = await client.get(
        "/api/v1/design/case",
        params={"project": str(project.id)},
        headers=bearer(owner),
    )
    body = response.json()
    assert response.status_code == 200, response.text
    assert body["version"] == 1
    assert body["content"] == example_case()
    assert body["files"] == [{"name": DEMAND_FILE, "size": len(DEMAND_CSV)}]
    versions = await CaseVersionRepository(session).list_versions(project.id)
    assert [row.author_id for row in versions] == [owner.id]
    activity = await ActivityRepository(session).latest(project.id, 10)
    assert [item.text for item in activity] == ["Saved case version 1"]


async def test_a_changed_case_adds_a_version_and_a_refused_one_none(
    session_factory, session, blobs, make_user, make_project, make_chat
) -> None:
    _, project, chat, recorder = await recorder_for(
        session_factory, blobs, make_user, make_project, make_chat
    )
    await save_artifact(session_factory, chat.id, f"case/{DEMAND_FILE}", DEMAND_CSV)
    changed = {**example_case(), "name": "changed"}

    await recorder.on_event(None, case_set(example_case()))
    await recorder.on_event(None, case_set(changed))
    await recorder.on_event(None, case_set(broken_case()))

    latest = await CaseVersionRepository(session).latest_version(project.id)
    assert latest.number == 2
    assert latest.content["name"] == "changed"


async def test_a_built_plant_becomes_the_project_plant_once(
    client, session_factory, session, blobs, make_user, make_project, make_chat
) -> None:
    owner, project, chat, recorder = await recorder_for(
        session_factory, blobs, make_user, make_project, make_chat
    )
    design = gm.Plant.from_dict(example_plant()).to_dict(structure=True)
    await save_artifact(session_factory, chat.id, "design/first", design)

    await recorder.on_event(None, plant_built("first"))
    await recorder.on_event(None, plant_built("first"))

    response = await client.get(
        "/api/v1/plant/flowsheet",
        params={"project": str(project.id)},
        headers=bearer(owner),
    )
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 1
    rows = await PlantVersionRepository(session).list_versions(project.id)
    assert [(row.number, row.note) for row in rows] == [
        (1, "Plant first built by the assistant")
    ]


async def test_a_failed_build_or_another_tool_saves_no_plant(
    session_factory, session, blobs, make_user, make_project, make_chat
) -> None:
    _, project, chat, recorder = await recorder_for(
        session_factory, blobs, make_user, make_project, make_chat
    )
    design = gm.Plant.from_dict(example_plant()).to_dict(structure=True)
    await save_artifact(session_factory, chat.id, "design/first", design)

    await recorder.on_event(None, plant_built("first", is_error=True))
    await recorder.on_event(None, plant_built("first", tool="read_plant"))
    await recorder.on_event(None, plant_built("missing"))

    assert await PlantVersionRepository(session).latest_version(project.id) is None


async def test_a_patched_or_simulated_design_becomes_the_project_plant(
    session_factory, session, blobs, make_user, make_project, make_chat
) -> None:
    """QA-092: the design the agents patched and simulated is the project plant."""
    _, project, chat, recorder = await recorder_for(
        session_factory, blobs, make_user, make_project, make_chat
    )
    first = gm.Plant.from_dict(example_plant()).to_dict(structure=True)
    renamed = {**example_plant(), "name": "gas_free"}
    patched = gm.Plant.from_dict(renamed).to_dict(structure=True)
    await save_artifact(session_factory, chat.id, "design/first", first)
    await save_artifact(session_factory, chat.id, "design/gas_free", patched)

    await recorder.on_event(None, plant_built("gas_free", tool="patch_plant"))
    await recorder.on_event(
        None, plant_built("", tool="simulate", given={"design": "design/first"})
    )
    await recorder.on_event(None, plant_built("", tool="simulate", given={}))
    await recorder.on_event(None, plant_built("first", tool="union_designs"))

    rows = await PlantVersionRepository(session).list_versions(project.id)
    assert [(row.number, row.note) for row in rows] == [
        (1, "Plant gas_free changed by the assistant"),
        (2, "Plant first simulated by the assistant"),
    ]
