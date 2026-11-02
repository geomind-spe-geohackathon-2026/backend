from uuid import uuid4

from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.chat import ChatRepository
from src.core.clients.postgres.repositories.run import RunRepository
from tests.conftest import bearer

OVERVIEW = "/api/v1/workspace/overview"


async def test_empty_project_overview(client, make_user, make_project) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.get(
        OVERVIEW, params={"project": str(project.id)}, headers=bearer(owner)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["chats"] == body["activity"] == body["active_runs"] == []
    assert body["progress"]["case"]["state"] == "empty"


async def test_overview_lists_latest_chats_activity_and_active_runs(
    client,
    make_user,
    make_project,
    session,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chats = ChatRepository(session)
    runs = RunRepository(session)
    for index in range(6):
        chat = await chats.create(project.id, f"Chat {index}", owner.id)
    active = await runs.create(uuid4(), chat.id, project.id, owner.id)
    finished = await runs.create(uuid4(), chat.id, project.id, owner.id)
    await runs.update(finished, {"status": "done"})
    activity = ActivityRepository(session)
    for index in range(12):
        await activity.add(project.id, "user", "Sahand", f"Change {index}")
    await activity.add(project.id, "agent", "Designer", "Case saved", "case", "3")

    response = await client.get(
        OVERVIEW, params={"project": str(project.id)}, headers=bearer(owner)
    )

    body = response.json()
    assert len(body["chats"]) == 5
    assert body["chats"][0]["last_run"] == {"id": str(finished.id), "status": "done"}
    assert [run["id"] for run in body["active_runs"]] == [str(active.id)]
    assert body["active_runs"][0]["usage"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "cost": 0.0,
    }
    assert len(body["activity"]) == 10
    assert body["activity"][0]["actor"] == {"kind": "agent", "name": "Designer"}
    assert body["activity"][0]["link"] == {"route": "case", "id": "3"}
    assert body["activity"][1]["link"] is None


async def test_overview_hides_other_projects(client, make_user, make_project) -> None:
    owner = await make_user()
    stranger = await make_user("other@example.com")
    project = await make_project(owner)

    response = await client.get(
        OVERVIEW, params={"project": str(project.id)}, headers=bearer(stranger)
    )

    assert response.status_code == 404
