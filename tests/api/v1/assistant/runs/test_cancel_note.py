from src.api.v1.assistant.runs.adapters.callbacks import note_cancel
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.run_event import RunEventRepository


def decided(tool: str | None, decision: str, reason: str | None) -> dict:
    return {
        "type": "permission",
        "rule": "user",
        "decision": decision,
        "tool": tool,
        "reason": reason,
    }


async def test_a_cancelled_run_says_so_with_the_users_denials(
    session_factory, session, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    run = await make_run(chat, owner)
    rows = [
        decided("set_ranges", "deny", "Do not change the plant"),
        decided("simulate", "allow", None),
        decided(None, "deny", None),
        decided("set_ranges", "deny", "I already said no"),
        decided("patch_plant", "deny", "cancelled"),
    ]
    events = RunEventRepository(session)
    for sequence, data in enumerate(rows, start=1):
        await events.add(run.id, sequence, "permission", False, data)

    await note_cancel(session_factory, run.id)
    await note_cancel(session_factory, run.id)

    found = [
        item
        for item in await MessageRepository(session).history(chat.id)
        if item.role == "assistant"
    ]
    assert [item.content for item in found] == [
        "Cancelled by the user.\n"
        "Denied: set_ranges (Do not change the plant)\n"
        "Denied: set_ranges (I already said no)"
    ]
    assert found[0].run_id == run.id
