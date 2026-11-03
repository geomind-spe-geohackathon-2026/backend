import geomind as gd
import pytest

from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.progress.project_state import project_state
from tests.conftest import bearer

URL = "/api/v1/assistant/suggestions"
CASE = {"format": 1, "kind": "case", "name": "c"}


@pytest.fixture
def heard(monkeypatch) -> list[tuple]:
    calls: list[tuple] = []

    def suggest(problem, files, project=None):
        calls.append((problem, files, project))
        return [{"label": "Build the case", "message": "Build the case from my files."}]

    monkeypatch.setattr(gd, "suggest", suggest, raising=False)
    return calls


async def test_a_new_chat_gets_next_steps_from_the_whole_project(
    client, make_user, make_project, heard
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response = await client.get(
        URL, params={"project": str(project.id)}, headers=bearer(owner)
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "suggestions": [
            {"label": "Build the case", "message": "Build the case from my files."}
        ]
    }
    problem, files, state = heard[0]
    assert (problem, files) == ({}, [])
    assert state["case"]["state"] == "empty"
    assert state["case_changed_after_study"] is False


async def test_an_empty_chat_state_carries_next_steps(
    client, make_user, make_project, make_chat, heard
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)

    state = await client.get(
        f"/api/v1/assistant/chat/{chat.id}/state", headers=bearer(owner)
    )

    assert state.json()["suggestions"][0]["label"] == "Build the case"


async def test_a_chat_with_messages_gets_none_in_its_state(
    client, session, make_user, make_project, make_chat, heard
) -> None:
    owner = await make_user()
    chat = await make_chat(await make_project(owner), owner)
    await MessageRepository(session).add(chat.id, "user", "hello", None)

    state = await client.get(
        f"/api/v1/assistant/chat/{chat.id}/state", headers=bearer(owner)
    )

    assert state.json()["suggestions"] == []


async def test_without_geomind_suggest_there_are_none(
    client, make_user, make_project, monkeypatch
) -> None:
    monkeypatch.delattr(gd, "suggest", raising=False)
    owner = await make_user()
    project = await make_project(owner)

    response = await client.get(
        URL, params={"project": str(project.id)}, headers=bearer(owner)
    )

    assert response.json() == {"suggestions": []}


async def test_a_chat_of_another_project_is_refused(
    client, make_user, make_project, make_chat, heard
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    other = await make_chat(await make_project(owner, "Other"), owner)

    response = await client.get(
        URL,
        params={"project": str(project.id), "chat": str(other.id)},
        headers=bearer(owner),
    )

    assert response.status_code == 404


async def test_the_state_says_when_the_case_changed_after_the_study(
    session, make_user, make_project
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    cases = CaseVersionRepository(session)
    await cases.save_version(project.id, CASE, "first", owner.id)
    await StudyRepository(session).create(
        {
            "project_id": project.id,
            "kind": "run",
            "name": "s",
            "settings": {},
            "status": "done",
            "started_by_kind": "user",
            "started_by_name": "u",
            "case_version": 1,
        }
    )
    await cases.save_version(project.id, {**CASE, "name": "c2"}, "second", owner.id)

    state = await project_state(session, project.id)

    assert (state["case_version"], state["study_case_version"]) == (2, 1)
    assert state["case_changed_after_study"] is True
    assert set(state) >= {"case", "plant", "study", "results", "report"}
