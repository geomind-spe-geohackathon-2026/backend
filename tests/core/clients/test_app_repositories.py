from uuid import uuid4

import pytest

from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.chat import ChatRepository
from src.core.clients.postgres.repositories.chat_state import ChatStateRepository
from src.core.clients.postgres.repositories.message import MessageRepository
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.run_artifact import RunArtifactRepository
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.errors import ConflictError
from src.core.pagination.page import PageRequest


@pytest.fixture
async def owner(make_user):
    return await make_user()


@pytest.fixture
async def project(owner, make_project):
    return await make_project(owner)


@pytest.fixture
async def chat(session, project, owner):
    return await ChatRepository(session).create(project.id, "First", owner.id)


@pytest.fixture
async def run(session, chat, project, owner):
    return await RunRepository(session).create(uuid4(), chat.id, project.id, owner.id)


async def test_case_versions_number_and_refuse_identical_content(
    session,
    project,
    owner,
) -> None:
    repository = CaseVersionRepository(session)

    first = await repository.save_version(project.id, {"a": 1}, "One", owner.id)
    second = await repository.save_version(project.id, {"a": 2}, "Two", owner.id)

    assert (first.number, second.number) == (1, 2)
    assert (await repository.latest_version(project.id)).number == 2
    with pytest.raises(ConflictError) as error:
        await repository.save_version(project.id, {"a": 2}, "Same", owner.id)
    assert error.value.details == {"latest": 2}


async def test_case_files_belong_to_one_version(session, project, owner) -> None:
    version = await CaseVersionRepository(session).save_version(
        project.id, {"a": 1}, "", owner.id
    )
    repository = CaseFileRepository(session)

    await repository.add(project.id, version.id, "b.csv", 5, "key/b")
    await repository.add(project.id, version.id, "a.csv", 7, "key/a")

    assert [file.name for file in await repository.list_for_version(version.id)] == [
        "a.csv",
        "b.csv",
    ]
    assert (await repository.get(version.id, "a.csv")).size == 7
    assert await repository.get(version.id, "none.csv") is None


async def test_chats_list_rename_and_delete(session, project, owner) -> None:
    repository = ChatRepository(session)
    first = await repository.create(project.id, "One", owner.id)
    await repository.create(project.id, "Two", owner.id)

    titles = [
        chat.title for chat in await repository.list_page(project.id, PageRequest())
    ]
    await repository.rename(first, "Renamed")
    await repository.delete(first.id)

    assert titles == ["One", "Two"]
    assert await repository.get_by_id(first.id) is None
    assert len(await repository.latest(project.id, 5)) == 1


async def test_messages_keep_their_order_and_run(session, chat, run) -> None:
    repository = MessageRepository(session)
    await repository.add(chat.id, "user", "Hello", run.id)
    await repository.add(chat.id, "assistant", "Hi", run.id)

    page = await repository.list_page(chat.id, PageRequest(limit=1))
    history = await repository.history(chat.id)

    assert [message.content for message in page] == ["Hello", "Hi"]
    assert [message.role for message in history] == ["user", "assistant"]
    assert history[0].run_id == run.id


async def test_runs_track_status_usage_and_activity(session, chat, project, owner):
    repository = RunRepository(session)
    first = await repository.create(uuid4(), chat.id, project.id, owner.id)
    second = await repository.create(uuid4(), chat.id, project.id, owner.id)

    assert await repository.has_active(chat.id)
    await repository.update(first, {"status": "done", "input_tokens": 10, "cost": 0.5})
    await repository.update(
        second, {"status": "done", "output_tokens": 4, "cost": 0.25}
    )

    assert not await repository.has_active(chat.id)
    assert await repository.usage(project.id) == (2, 10, 4, 0.75)
    newest = await repository.list_page(project.id, PageRequest())
    assert [item.id for item in newest] == [second.id, first.id]
    assert await repository.list_page(project.id, PageRequest(), active_only=True) == []
    assert (await repository.last_for_chats([chat.id]))[chat.id].id == second.id


async def test_run_events_replay_after_a_sequence(session, run) -> None:
    repository = RunEventRepository(session)
    await repository.add(run.id, 1, "run.started", True, {"sequence": 1})
    await repository.add(run.id, 3, "llm.completed", False, {"sequence": 3})
    await repository.add(run.id, 5, "run.finished", True, {"sequence": 5})

    after_one = await repository.after(run.id, 1)
    public = await repository.after(run.id, 0, public_only=True)

    assert [event.sequence for event in after_one] == [3, 5]
    assert [event.sequence for event in public] == [1, 5]
    assert public[0].data == {"sequence": 1}


async def test_artifacts_are_read_by_run_and_by_chat(session, chat, project, owner):
    runs = RunRepository(session)
    first = await runs.create(uuid4(), chat.id, project.id, owner.id)
    second = await runs.create(uuid4(), chat.id, project.id, owner.id)
    repository = RunArtifactRepository(session)
    await repository.save(first.id, chat.id, "case/a.csv", b"old")
    await repository.save(first.id, chat.id, "result/1", {"k": 1})
    await repository.save(second.id, chat.id, "case/a.csv", b"mine")
    await repository.save(None, chat.id, "case/a.csv", b"new")

    assert (await repository.newest_for_run(first.id, "case/a.csv")).data == b"old"
    assert (await repository.newest_for_chat(chat.id, "case/a.csv")).data == b"new"
    assert (await repository.newest_for_run(first.id, "result/1")).data == {"k": 1}
    assert await repository.newest_for_run(second.id, "result/1") is None
    assert (await repository.newest_for_run(second.id, "case/a.csv")).data == b"mine"
    assert await repository.newest_for_chat(chat.id, "result/1") is None
    assert await repository.newest_for_chat(chat.id, "missing") is None


async def test_chat_state_versions_rise(session, chat) -> None:
    repository = ChatStateRepository(session)

    assert await repository.latest(chat.id) is None
    await repository.save(chat.id, {"goal": "a"})
    second = await repository.save(chat.id, {"goal": "b"})

    assert second.version == 2
    assert (await repository.latest(chat.id)).state == {"goal": "b"}


async def test_studies_and_results_link(session, project) -> None:
    studies = StudyRepository(session)
    study = await studies.create(
        {
            "project_id": project.id,
            "kind": "run",
            "name": "S",
            "settings": {},
            "status": "queued",
            "started_by_kind": "user",
            "started_by_name": "Member",
        }
    )
    assert study.progress_total == 1 and study.missing == []
    assert await studies.has_active(project.id)

    await studies.update(study, {"status": "done", "progress_done": 1})
    result = await ResultRepository(session).create(
        {
            "project_id": project.id,
            "study_id": study.id,
            "name": "R",
            "summary": {"kpis": []},
            "content": {},
        }
    )
    results = ResultRepository(session)

    assert not await studies.has_active(project.id)
    assert (await results.get_for_study(study.id)).id == result.id
    assert [item.id for item in await results.by_ids(project.id, [result.id])] == [
        result.id
    ]
    assert len(await studies.list_page(project.id, PageRequest())) == 1
    assert len(await results.list_page(project.id, PageRequest())) == 1


async def test_documents_are_searched_by_words(session, project, owner) -> None:
    repository = RagDocumentRepository(session)
    first = await repository.create(project.id, "a.txt", 3, "k/a", owner.id)
    second = await repository.create(project.id, "b.txt", 3, "k/b", owner.id)
    third = await repository.create(project.id, "c.txt", 3, "k/c", owner.id)

    assert first.searchable == "pending"
    await repository.set_text(first, "Heat pump sizing")
    await repository.set_text(second, "Pump curve")
    await repository.set_text(third, None)

    assert third.searchable == "failed"
    both = await repository.search(project.id, ["pump", "HEAT"])
    assert [document.name for document in both] == ["a.txt"]
    assert len(await repository.search(project.id, ["pump"])) == 2
    await repository.delete(first.id)
    assert await repository.get_by_id(first.id) is None


async def test_activity_lists_newest_first(session, project) -> None:
    repository = ActivityRepository(session)
    await repository.add(project.id, "user", "Member", "Saved the case", "case", "2")
    await repository.add(project.id, "agent", "Analyst", "Finished a run")

    rows = await repository.latest(project.id, 10)

    assert [row.text for row in rows] == ["Finished a run", "Saved the case"]
    assert rows[1].link_route == "case" and rows[0].link_id is None
