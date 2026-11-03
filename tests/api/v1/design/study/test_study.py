from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.api.v1.design.study import services
from src.core.clients.postgres.models.study import Study
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.gemini import study as gemini_study
from tests import design_inputs
from tests.api.v1.design.study.conftest import study_body
from tests.conftest import bearer
from tests.routes import route_exists

URL = "/api/v1/design/study"


def never_cancelled(_job: str) -> bool:
    return False


async def test_kinds_are_geminis_methods(client, make_user) -> None:
    user = await make_user()

    response = await client.get(f"{URL}/kinds", headers=bearer(user))

    kinds = response.json()
    assert [kind["kind"] for kind in kinds] == [
        "run",
        "minimize",
        "sample",
        "sensitivity",
        "size",
    ]
    assert kinds[0]["schema"]["title"] == "Study"
    assert kinds[0]["description"]
    by_kind = {kind["kind"]: set(kind["schema"]["properties"]) for kind in kinds}
    assert by_kind["sample"] == {"metrics", "samples", "seed", "prepare"}
    assert by_kind["minimize"] == {"objective", "evaluations", "seed", "prepare"}
    assert by_kind["size"] == set()


async def test_ready_study_is_queued(
    client, make_user, make_project, save_inputs, queued
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)

    response = await client.post(URL, json=study_body(project), headers=bearer(user))

    body = response.json()
    assert response.status_code == 201
    assert body["status"] == "queued"
    assert body["progress"] == {"done": 0, "total": 1}
    assert body["case_version"] == 1
    assert body["plant_version"] == 1
    assert body["started_by"] == {"kind": "user", "name": "member", "run": None}
    assert queued == [UUID(body["id"])]


async def test_a_study_can_run_on_an_older_plant_version(
    client, make_user, make_project, save_inputs, queued, session_factory
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)
    async with session_factory() as session:
        await PlantVersionRepository(session).save_version(
            project.id,
            {**design_inputs.plant_content(), "name": "second"},
            "second",
            user.id,
        )

    pinned = await client.post(
        URL, json={**study_body(project), "plant_version": 1}, headers=bearer(user)
    )
    latest = await client.post(
        URL, json={**study_body(project), "name": "latest"}, headers=bearer(user)
    )

    assert pinned.status_code == 201, pinned.text
    assert pinned.json()["plant_version"] == 1
    assert pinned.json()["plant_pinned"] is True
    assert latest.json()["plant_version"] == 2
    assert latest.json()["plant_pinned"] is False


async def test_a_plant_version_the_project_lacks_is_refused(
    client, make_user, make_project, save_inputs
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)

    response = await client.post(
        URL, json={**study_body(project), "plant_version": 7}, headers=bearer(user)
    )

    assert response.status_code == 422
    assert "plant_version" in response.json()["error"]["details"]["fields"]


async def test_a_blocked_study_keeps_its_chosen_plant_version(
    client, make_user, make_project, save_inputs, queued, session_factory, blobs
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user, files=False)
    async with session_factory() as session:
        await PlantVersionRepository(session).save_version(
            project.id,
            {**design_inputs.plant_content(), "name": "second"},
            "second",
            user.id,
        )
    created = await client.post(
        URL, json={**study_body(project), "plant_version": 1}, headers=bearer(user)
    )
    assert created.json()["status"] == "blocked"
    async with session_factory() as session:
        case = await CaseVersionRepository(session).latest_version(project.id)
        for name, data in design_inputs.case_files().items():
            blobs.objects[f"{project.id}/{name}"] = data
            await CaseFileRepository(session).add(
                project.id, case.id, name, len(data), f"{project.id}/{name}"
            )

    started = await client.post(
        f"{URL}/{created.json()['id']}/start", headers=bearer(user)
    )

    assert started.json()["status"] == "queued", started.text
    assert started.json()["plant_version"] == 1


async def test_study_without_case_is_blocked_with_missing(
    client, make_user, make_project, queued
) -> None:
    user = await make_user()
    project = await make_project(user)

    response = await client.post(URL, json=study_body(project), headers=bearer(user))

    body = response.json()
    assert response.status_code == 201
    assert body["status"] == "blocked"
    assert [item["path"] for item in body["missing"]] == ["plant", "case"]
    assert queued == []


async def test_study_missing_case_files_is_blocked(
    client, make_user, make_project, save_inputs, queued
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user, files=False)

    response = await client.post(URL, json=study_body(project), headers=bearer(user))

    body = response.json()
    assert body["status"] == "blocked"
    assert body["missing"][0]["path"] == "demand.heating.power.file"


async def test_study_without_case_files_never_reads_the_store(
    client, make_user, make_project, save_inputs, queued, blobs, monkeypatch
) -> None:
    async def refuse(key: str) -> bytes:
        raise AssertionError("the object store was read")

    monkeypatch.setattr(blobs, "get", refuse)
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user, files=False)

    response = await client.post(URL, json=study_body(project), headers=bearer(user))

    assert response.status_code == 201


async def test_blocked_study_starts_once_inputs_exist(
    client, make_user, make_project, save_inputs, queued
) -> None:
    user = await make_user()
    project = await make_project(user)
    created = await client.post(URL, json=study_body(project), headers=bearer(user))
    study_id = created.json()["id"]
    still = await client.post(f"{URL}/{study_id}/start", headers=bearer(user))
    await save_inputs(project, user)

    started = await client.post(f"{URL}/{study_id}/start", headers=bearer(user))

    assert still.status_code == 422
    assert still.json()["error"]["code"] == "missing_inputs"
    assert started.json()["status"] == "queued"
    assert started.json()["missing"] == []
    assert queued == [UUID(study_id)]


async def test_start_refuses_a_study_that_is_not_blocked(
    client, make_user, make_project, save_inputs, queued
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)
    created = await client.post(URL, json=study_body(project), headers=bearer(user))

    response = await client.post(
        f"{URL}/{created.json()['id']}/start", headers=bearer(user)
    )

    assert response.status_code == 409


async def test_settings_gemini_refuses_are_validation_failed(
    client, make_user, make_project, queued
) -> None:
    user = await make_user()
    project = await make_project(user)

    response = await client.post(
        URL, json=study_body(project, kind="minimize"), headers=bearer(user)
    )

    error = response.json()["error"]
    assert response.status_code == 422
    assert error["code"] == "validation_failed"
    assert "objective" in error["details"]["fields"]


async def test_unknown_kind_is_validation_failed(
    client, make_user, make_project
) -> None:
    user = await make_user()
    project = await make_project(user)

    response = await client.post(
        URL, json=study_body(project, kind="unknown"), headers=bearer(user)
    )

    assert response.json()["error"]["details"]["fields"] == {
        "kind": "Unknown study kind"
    }


async def test_list_and_get(
    client, make_user, make_project, save_inputs, queued
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)
    created = await client.post(URL, json=study_body(project), headers=bearer(user))

    listed = await client.get(f"{URL}?project={project.id}", headers=bearer(user))
    fetched = await client.get(f"{URL}/{created.json()['id']}", headers=bearer(user))

    assert [item["id"] for item in listed.json()["items"]] == [created.json()["id"]]
    assert fetched.json()["name"] == "Base"


async def test_redis_progress_shows_while_running(
    client, make_user, make_project, save_inputs, queued, redis
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)
    created = await client.post(URL, json=study_body(project), headers=bearer(user))
    study_id = created.json()["id"]
    await redis.set(f"job:{study_id}:progress", '{"done": 2, "total": 5}')

    fetched = await client.get(f"{URL}/{study_id}", headers=bearer(user))

    assert fetched.json()["progress"] == {"done": 2, "total": 5}


async def test_other_users_study_is_not_found(
    client, make_user, make_project, save_inputs, queued
) -> None:
    owner = await make_user()
    stranger = await make_user("stranger@example.com")
    project = await make_project(owner)
    await save_inputs(project, owner)
    created = await client.post(URL, json=study_body(project), headers=bearer(owner))

    response = await client.get(
        f"{URL}/{created.json()['id']}", headers=bearer(stranger)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "study_not_found"


async def test_cancel_flags_the_study_without_killing_the_worker(
    client,
    make_user,
    make_project,
    save_inputs,
    queued,
    terminated,
    killed_later,
    redis,
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)
    created = await client.post(URL, json=study_body(project), headers=bearer(user))
    study_id = created.json()["id"]

    response = await client.post(f"{URL}/{study_id}/cancel", headers=bearer(user))

    assert response.json()["status"] == "cancelled"
    assert response.json()["ended"] is not None
    assert terminated == []
    assert killed_later == ["task-1"]
    assert await redis.exists(f"job:{study_id}:cancel")
    again = await client.post(f"{URL}/{study_id}/cancel", headers=bearer(user))
    assert again.status_code == 409


async def make_queued(
    session_factory: async_sessionmaker, project: Any, owner: Any
) -> Study:
    async with session_factory() as session:
        return await StudyRepository(session).create(
            {
                "project_id": project.id,
                "kind": "run",
                "name": "Base",
                "settings": {},
                "status": "queued",
                "started_by_kind": "user",
                "started_by_name": owner.name,
                "case_version": 1,
                "plant_version": 1,
            }
        )


async def test_worker_stores_the_result(
    session_factory, session, make_user, make_project, save_inputs, blobs, monkeypatch
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)
    study = await make_queued(session_factory, project, user)
    monkeypatch.setattr(gemini_study, "run", lambda *_: design_inputs.outcome())
    reported = []

    async with session_factory() as worker:
        await services.run_study(
            study.id,
            services.Stores.open(worker),
            blobs,
            lambda *args: reported.append(args),
            never_cancelled,
        )

    stores = services.Stores.open(session)
    done = await stores.studies.refresh(await stores.studies.get_by_id(study.id))
    result = await stores.results.get_for_study(study.id)
    assert done.status == "done"
    assert (done.progress_done, done.progress_total) == (1, 1)
    assert result.summary["checks"]["passed"] == 13
    assert "coverage" not in result.content
    assert reported == [(str(study.id), 0, 1)]
    activity = await stores.activity.latest(project.id, 1)
    assert (activity[0].link_route, activity[0].link_id) == (
        "design/results",
        str(result.id),
    )
    assert route_exists(activity[0].link_route, activity[0].link_id)


async def test_worker_records_a_failed_study(
    session_factory, session, make_user, make_project, save_inputs, blobs, monkeypatch
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)
    study = await make_queued(session_factory, project, user)

    def fail(*_: Any) -> None:
        raise gemini_study.StudyRunError("no convergence", details={"code": "step"})

    monkeypatch.setattr(gemini_study, "run", fail)

    async with session_factory() as worker:
        await services.run_study(
            study.id,
            services.Stores.open(worker),
            blobs,
            lambda *_: None,
            never_cancelled,
        )

    stores = services.Stores.open(session)
    failed = await stores.studies.refresh(await stores.studies.get_by_id(study.id))
    assert failed.status == "failed"
    assert failed.error["code"] == "study_failed"
    assert failed.error["details"] == {"code": "step"}
    row = (await stores.activity.latest(project.id, 1))[0]
    assert (row.link_route, row.link_id) == ("design/study", None)
    assert route_exists(row.link_route, row.link_id)


async def test_worker_leaves_a_cancelled_study_alone(
    session_factory, make_user, make_project, blobs, monkeypatch
) -> None:
    user = await make_user()
    project = await make_project(user)
    study = await make_queued(session_factory, project, user)
    async with session_factory() as session:
        await StudyRepository(session).update(
            await StudyRepository(session).get_by_id(study.id), {"status": "cancelled"}
        )
    monkeypatch.setattr(gemini_study, "run", lambda *_: 1 / 0)

    async with session_factory() as worker:
        await services.run_study(
            study.id,
            services.Stores.open(worker),
            blobs,
            lambda *_: None,
            never_cancelled,
        )


async def test_a_cancelled_study_stops_without_a_result_or_a_failure(
    session, session_factory, make_user, make_project, save_inputs, blobs, monkeypatch
) -> None:
    user = await make_user()
    project = await make_project(user)
    await save_inputs(project, user)
    study = await make_queued(session_factory, project, user)

    def stopped(*_: object) -> None:
        raise gemini_study.StudyCancelledError("stopped")

    monkeypatch.setattr(gemini_study, "run", stopped)

    async with session_factory() as worker:
        await services.run_study(
            study.id,
            services.Stores.open(worker),
            blobs,
            lambda *_: None,
            never_cancelled,
        )

    stores = services.Stores.open(session)
    cancelled = await stores.studies.refresh(await stores.studies.get_by_id(study.id))
    assert cancelled.status == "cancelled"
    assert cancelled.error is None
    assert await stores.results.get_for_study(study.id) is None
