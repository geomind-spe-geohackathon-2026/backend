"""A real geomind run on the scripted LLM, whose events the tests store."""

from typing import Any
from uuid import UUID

import geomind as gd

from src.api.v1.assistant.runs.adapters.fake import scripted_llm


async def play(run_id: UUID, answer_request: bool = True) -> list[Any]:
    """Return the events of a scripted run: paused at the approval, or finished."""
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
    run.id = run_id.hex
    paused = await run.astart()
    if answer_request:
        resumed = gd.Run.load(
            run.id,
            llm=scripted_llm(True, ""),
            store=store,
            permissions=permissions,
        )
        await resumed.aresume(paused.request.id, {"approved": True})
    return store.load_events(run.id)
