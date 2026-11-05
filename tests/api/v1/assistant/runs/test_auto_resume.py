"""Turning auto-approve on hands a waiting run to geomind with no answer (QA-354)."""

from tests.api.v1.assistant.conftest import run_url
from tests.conftest import bearer

CHAT = "/api/v1/assistant/chat"
REQUEST = {"request": "request-14", "kind": "question", "message": "Which year?"}


async def test_auto_approve_on_resumes_the_chats_waiting_run(
    client, make_user, make_project, make_chat, make_run, queue
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    run = await make_run(chat, owner, "waiting", {"request": REQUEST})

    response = await client.put(
        f"{CHAT}/{chat.id}/auto-approve", json={"auto_approve": True}, headers=bearer(owner)
    )
    after = await client.get(run_url(run.id), headers=bearer(owner))

    assert response.json() == {"auto_approve": True}
    assert after.json()["status"] == "running"
    assert queue.sent == [("assistant.runs.resume", str(run.id), None, None)]


async def test_auto_approve_off_leaves_a_waiting_run(
    client, make_user, make_project, make_chat, make_run, queue
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    run = await make_run(chat, owner, "waiting", {"request": REQUEST})

    await client.put(
        f"{CHAT}/{chat.id}/auto-approve", json={"auto_approve": False}, headers=bearer(owner)
    )
    after = await client.get(run_url(run.id), headers=bearer(owner))

    assert after.json()["status"] == "waiting"
    assert queue.sent == []
