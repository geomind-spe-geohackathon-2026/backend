import geomind as gd

from src.api.v1.assistant.runs.adapters.fake import scripted_llm
from tests.plants import example_plant


async def test_scripted_run_lists_the_project_plants_before_it_asks_to_save() -> None:
    plant = example_plant()
    workspace = gd.stores.MemoryWorkspace(plants={"p1": {plant["name"]: plant}})
    run = gd.Run(
        message="Size the plant",
        chat="c1",
        project="p1",
        llm=scripted_llm(False),
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
