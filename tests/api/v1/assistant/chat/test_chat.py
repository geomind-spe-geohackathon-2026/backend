from uuid import uuid4

from src.core.clients.postgres.repositories.chat_state import ChatStateRepository
from tests.conftest import bearer

CHAT = "/api/v1/assistant/chat"


async def test_create_and_list_chats(client, make_user, make_project) -> None:
    owner = await make_user()
    project = await make_project(owner)
    headers = bearer(owner)

    created = await client.post(
        CHAT, json={"project": str(project.id), "title": "Sizing"}, headers=headers
    )
    listed = await client.get(f"{CHAT}?project={project.id}", headers=headers)

    assert created.status_code == 201
    assert created.json()["last_run"] is None
    assert [item["title"] for item in listed.json()["items"]] == ["Sizing"]


async def test_chat_without_title_gets_a_technical_title(
    client, make_user, make_project
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    created = await client.post(
        CHAT, json={"project": str(project.id)}, headers=bearer(owner)
    )

    assert created.json()["title"] == "New chat"


async def test_other_member_cannot_create_a_chat(
    client, make_user, make_project
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    project = await make_project(owner)

    response = await client.post(
        CHAT, json={"project": str(project.id)}, headers=bearer(other)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


async def test_other_member_sees_chat_not_found(
    client, make_user, make_project, make_chat
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    chat = await make_chat(await make_project(owner), owner)

    response = await client.get(f"{CHAT}/{chat.id}/messages", headers=bearer(other))
    missing = await client.get(f"{CHAT}/{uuid4()}/messages", headers=bearer(other))

    assert response.status_code == missing.status_code == 404
    assert response.json()["error"]["code"] == "chat_not_found"


async def test_rename_and_delete(client, make_user, make_project, make_chat) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    headers = bearer(owner)

    renamed = await client.patch(
        f"{CHAT}/{chat.id}", json={"title": "New"}, headers=headers
    )
    deleted = await client.delete(f"{CHAT}/{chat.id}", headers=headers)
    gone = await client.get(f"{CHAT}/{chat.id}/messages", headers=headers)

    assert renamed.json()["title"] == "New"
    assert deleted.status_code == 204
    assert gone.status_code == 404


async def test_delete_is_refused_while_a_run_is_active(
    client, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    await make_run(chat, owner, "waiting")

    response = await client.delete(f"{CHAT}/{chat.id}", headers=bearer(owner))

    assert response.status_code == 409


async def test_message_creates_a_queued_run(
    client, make_user, make_project, make_chat, queue
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    headers = bearer(owner)

    sent = await client.post(
        f"{CHAT}/{chat.id}/messages", json={"content": "Hello"}, headers=headers
    )

    body = sent.json()
    assert sent.status_code == 201
    assert body["message"]["run"] == body["run"]["id"]
    assert body["run"]["status"] == "queued"
    assert queue.sent == [("assistant.runs.start", body["run"]["id"])]
    messages = await client.get(f"{CHAT}/{chat.id}/messages", headers=headers)
    assert [item["content"] for item in messages.json()["items"]] == ["Hello"]
    listed = await client.get(f"{CHAT}?project={chat.project_id}", headers=headers)
    assert listed.json()["items"][0]["last_run"]["status"] == "queued"


async def test_second_message_waits_for_the_active_run(
    client, make_user, make_project, make_chat, queue
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    headers = bearer(owner)
    url = f"{CHAT}/{chat.id}/messages"
    await client.post(url, json={"content": "One"}, headers=headers)

    second = await client.post(url, json={"content": "Two"}, headers=headers)

    assert second.status_code == 409
    assert len(queue.sent) == 1


async def test_message_fails_the_run_when_the_queue_is_down(
    client, make_user, make_project, make_chat, queue
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    headers = bearer(owner)
    queue.down = True

    sent = await client.post(
        f"{CHAT}/{chat.id}/messages", json={"content": "Hello"}, headers=headers
    )
    runs = await client.get(
        f"/api/v1/assistant/runs?project={project.id}", headers=headers
    )

    assert sent.status_code == 503
    assert sent.json()["error"]["code"] == "unavailable"
    assert runs.json()["items"][0]["status"] == "failed"
    assert runs.json()["items"][0]["error"]["code"] == "unavailable"


async def test_state_is_empty_then_the_newest_version(
    client, make_user, make_project, make_chat, session
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    headers = bearer(owner)

    empty = await client.get(f"{CHAT}/{chat.id}/state", headers=headers)
    await ChatStateRepository(session).save(chat.id, {"goal": "heat"})
    await ChatStateRepository(session).save(chat.id, {"goal": "cool"})
    newest = await client.get(f"{CHAT}/{chat.id}/state", headers=headers)

    assert empty.json() == {"version": 0, "state": None, "suggestions": []}
    assert newest.json() == {"version": 2, "state": {"goal": "cool"}, "suggestions": []}


async def test_usage_totals_the_runs(
    client, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    values = {"input_tokens": 10, "output_tokens": 5, "cost": 0.5}
    await make_run(chat, owner, "done", values)
    await make_run(chat, owner, "done", values)

    response = await client.get(
        f"/api/v1/assistant/usage?project={project.id}", headers=bearer(owner)
    )

    assert response.json() == {
        "runs": 2,
        "input_tokens": 20,
        "output_tokens": 10,
        "cost": 1.0,
    }


async def test_first_message_titles_a_chat_that_has_the_technical_title(
    client, make_user, make_project, queue
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    headers = bearer(owner)
    created = await client.post(
        CHAT, json={"project": str(project.id)}, headers=headers
    )
    chat_id = created.json()["id"]
    text = "Please size a heating plant for the example district " + "x" * 80

    await client.post(
        f"{CHAT}/{chat_id}/messages", json={"content": text}, headers=headers
    )

    listed = await client.get(f"{CHAT}?project={project.id}", headers=headers)
    title = listed.json()["items"][0]["title"]
    assert title.startswith("Please size a heating plant")
    assert len(title) <= 60
    assert title.endswith("\u2026")


async def test_a_named_chat_keeps_its_title(
    client, make_user, make_project, queue
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    headers = bearer(owner)
    created = await client.post(
        CHAT, json={"project": str(project.id), "title": "Sizing"}, headers=headers
    )

    await client.post(
        f"{CHAT}/{created.json()['id']}/messages",
        json={"content": "Hello"},
        headers=headers,
    )

    listed = await client.get(f"{CHAT}?project={project.id}", headers=headers)
    assert listed.json()["items"][0]["title"] == "Sizing"
