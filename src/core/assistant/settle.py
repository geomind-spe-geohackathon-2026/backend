"""End a run the row shows ``waiting`` although its log ended (QA-077)."""

from typing import Any

from sqlalchemy import select

from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.models.run import Run
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.run_event import RunEventRepository


async def settled_ended(run: Run, session: Any) -> bool:
    """End a waiting run whose root ``run.finished`` is newer than its last request.

    geomind sends no ``run.finished`` when a run only pauses on a request, so a root one after
    the newest request means the run ended; the row had been left ``waiting`` and its chat
    refused every new message. Return whether the row was ended.
    """
    if run.status != "waiting":
        return False
    events = RunEventRepository(session)
    requests = await events.of_type(run.id, "request")
    finished = [
        row
        for row in await events.of_type(run.id, "run.finished")
        if row.data.get("parent") is None
    ]
    if not finished:
        return False
    last = finished[0]
    if requests and requests[0].sequence > last.sequence:
        return False
    status = last.data.get("status") or "failed"
    values: dict[str, Any] = {"status": status, "request": None, "ended": utc_now()}
    if status == "failed":
        values["error"] = {
            "code": last.data.get("stop_reason") or "error",
            "message": last.data.get("message") or "",
        }
    await RunRepository(session).update(run, values)
    return True


async def settle_chat(chat_id: Any, session: Any) -> None:
    """End every waiting run of a chat whose log ended, before the chat is judged busy."""
    rows = await session.scalars(
        select(Run).where(Run.chat_id == chat_id, Run.status == "waiting")
    )
    for run in list(rows):
        await settled_ended(run, session)
