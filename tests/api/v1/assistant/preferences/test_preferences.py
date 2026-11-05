"""A user's auto-approve answer is kept and new chats start with it (QA-292)."""

from tests.conftest import bearer

PREFERENCES = "/api/v1/assistant/preferences"
CHAT = "/api/v1/assistant/chat"


async def test_auto_approve_is_unset_until_answered_then_kept(client, make_user) -> None:
    user = await make_user()

    before = await client.get(PREFERENCES, headers=bearer(user))
    answered = await client.put(PREFERENCES, json={"auto_approve": True}, headers=bearer(user))
    after = await client.get(PREFERENCES, headers=bearer(user))

    assert before.json() == {"auto_approve": False, "auto_approve_set": False}
    assert answered.json() == {"auto_approve": True, "auto_approve_set": True}
    assert after.json() == {"auto_approve": True, "auto_approve_set": True}


async def test_a_no_is_kept_as_set(client, make_user) -> None:
    user = await make_user()

    response = await client.put(PREFERENCES, json={"auto_approve": False}, headers=bearer(user))

    assert response.json() == {"auto_approve": False, "auto_approve_set": True}
    bad = await client.put(PREFERENCES, json={"auto_approve": "yes", "x": 1}, headers=bearer(user))
    assert bad.status_code == 422


async def test_new_chats_take_the_user_preference(client, make_user, make_project) -> None:
    user = await make_user()
    project = await make_project(user)
    plain = await client.post(CHAT, json={"project": str(project.id)}, headers=bearer(user))
    await client.put(PREFERENCES, json={"auto_approve": True}, headers=bearer(user))
    on = await client.post(CHAT, json={"project": str(project.id)}, headers=bearer(user))

    def state(chat):
        return client.get(f"{CHAT}/{chat.json()['id']}/auto-approve", headers=bearer(user))

    assert (await state(plain)).json() == {"auto_approve": False}
    assert (await state(on)).json() == {"auto_approve": True}
