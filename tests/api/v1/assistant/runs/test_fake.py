from types import SimpleNamespace

import geomind as gd

from src.api.v1.assistant.runs.adapters.fake import (
    ANSWER,
    FAILED_ANSWER,
    last_step_failed,
    scripted_llm,
)
from tests.plants import example_plant


async def test_scripted_run_lists_the_project_plants_before_it_asks_to_save() -> None:
    plant = example_plant()
    workspace = gd.stores.MemoryWorkspace(plants={"p1": {plant["name"]: plant}})
    run = gd.Run(
        message="Save a demand profile",
        chat="c1",
        project="p1",
        llm=scripted_llm(False, "demand profile"),
        store=gd.stores.MemoryRunStore(),
        workspace=workspace,
        permissions=gd.Permissions(mode="ask"),
    )

    paused = await run.astart()

    events = run.store.load_events(run.id)
    tools = [event.tool for event in events if event.type == "tool.started"]
    listed = [event for event in events if event.type == "tool.finished"]
    assert tools[0] == "list_plants"
    assert plant["name"] in listed[0].output_summary
    assert paused.request is not None


async def test_a_greeting_gets_a_plain_scripted_answer() -> None:
    run = gd.Run(
        message="hi",
        chat="c1",
        project="p1",
        llm=scripted_llm(False, "hi"),
        store=gd.stores.MemoryRunStore(),
        permissions=gd.Permissions(mode="ask"),
    )

    result = await run.astart()

    assert result.status == "done"
    assert result.request is None
    assert "Demo mode" in result.answer


async def test_a_refused_save_ends_with_a_sentence_that_says_so() -> None:
    store = gd.stores.MemoryRunStore()
    permissions = gd.Permissions(mode="ask")
    run = gd.Run(
        message="Save a demand profile",
        chat="c1",
        project="p1",
        llm=scripted_llm(False, "demand profile"),
        store=store,
        permissions=permissions,
    )
    paused = await run.astart()

    resumed = gd.Run.load(
        run.id, llm=scripted_llm(True, ""), store=store, permissions=permissions
    )
    result = await resumed.aresume(paused.request.id, {"approved": True})

    assert result.answer == FAILED_ANSWER
    assert ANSWER not in result.answer


def message(role: str, content: str) -> SimpleNamespace:
    return SimpleNamespace(role=role, content=content)


def test_the_newest_tool_result_decides_the_ending() -> None:
    failed = message("tool", "{'error': {'code': 'invalid_input'}}")
    saved = message("tool", "{'time': {'start': '2027-01-01'}, 'steps': 365}")
    note = message("system", "Steps left: 27")

    assert last_step_failed([failed, note])
    assert not last_step_failed([saved, note])
    assert not last_step_failed([failed, saved, note])
    assert not last_step_failed([note])
