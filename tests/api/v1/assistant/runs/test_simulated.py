import hashlib
from types import SimpleNamespace

import gemini as gm

from src.api.v1.assistant.runs.adapters.simulated import SimulationRecorder
from src.core.case_versions import files_digest
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.plant_version import PlantVersionRepository
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.run_artifact import RunArtifactRepository
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.gemini import plant as plant_document
from tests import design_inputs

FINISHED = SimpleNamespace(type="run.finished", parent=None)


def simulated(name: str, reference: str, is_error: bool = False) -> dict:
    return {
        "type": "tool.result",
        "tool": "simulate",
        "source": "tool",
        "is_error": is_error,
        "input": {"design": f"design/{name}"},
        "output": {"reference": reference, "summary": {}},
    }


async def keep_run(session_factory, chat_id, identifier: str) -> None:
    built = gm.Plant.from_dict(design_inputs.plant_content())
    files = design_inputs.case_files()
    case = gm.Case.from_dict(design_inputs.case_content(), files=files)
    results = gm.simulate(built, case)
    digests = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    parts = {
        f"{identifier}.plant": built.to_dict(structure=True),
        f"{identifier}.case": design_inputs.case_content(),
        f"{identifier}.files": digests,
        f"{identifier}.results": results.to_bytes(),
    }
    for name, digest in digests.items():
        parts[f"{digest}.file"] = files[name]
    async with session_factory() as session:
        artifacts = RunArtifactRepository(session)
        for key, data in parts.items():
            await artifacts.save(None, chat_id, key, data)


async def test_the_last_simulate_of_a_run_becomes_one_result(
    session_factory, session, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    run = await make_run(chat, owner)
    case = design_inputs.case_content()
    await CaseVersionRepository(session).save_version(
        project.id,
        case,
        "first",
        owner.id,
        files_digest(case, design_inputs.case_files()),
    )
    content = plant_document.validate_content(
        gm.Plant.from_dict(design_inputs.plant_content()).to_dict(structure=True)
    )
    await PlantVersionRepository(session).save_version(
        project.id, content, "first", owner.id
    )
    await keep_run(session_factory, chat.id, "abc")
    events = RunEventRepository(session)
    rows = [
        simulated("old", "result/missing"),
        simulated("plant", "result/abc"),
        simulated("broken", "result/nothing", is_error=True),
    ]
    for sequence, data in enumerate(rows, start=1):
        await events.add(run.id, sequence, data["type"], False, data)
    recorder = SimulationRecorder(session_factory, run.id, chat.id, project.id)

    await recorder.on_event(None, FINISHED)
    await recorder.on_event(None, FINISHED)

    results = await ResultRepository(session).all_for_project(project.id)
    assert [(item.name, item.case_version, item.plant_version) for item in results] == [
        ("simulation plant", 1, 1)
    ]
    stored = results[0]
    assert stored.study_id is None
    assert stored.content["simulation"] == "result/abc"
    assert stored.content["coverage"]["heating"]
    assert stored.summary["checks"]["passed"] >= 0


async def test_a_run_without_simulate_or_nested_finish_records_nothing(
    session_factory, session, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    run = await make_run(chat, owner)
    recorder = SimulationRecorder(session_factory, run.id, chat.id, project.id)
    await RunEventRepository(session).add(
        run.id, 1, "tool.result", False, simulated("plant", "result/abc")
    )

    await recorder.on_event(None, SimpleNamespace(type="run.finished", parent="x"))
    await recorder.on_event(None, SimpleNamespace(type="tool.result", parent=None))

    assert await ResultRepository(session).all_for_project(project.id) == []


async def test_a_second_run_of_a_recorded_design_adds_no_result(
    session_factory, session, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    case = design_inputs.case_content()
    await CaseVersionRepository(session).save_version(
        project.id,
        case,
        "first",
        owner.id,
        files_digest(case, design_inputs.case_files()),
    )
    events = RunEventRepository(session)
    for identifier in ("abc", "def"):
        run = await make_run(chat, owner)
        await keep_run(session_factory, chat.id, identifier)
        data = simulated(identifier, f"result/{identifier}")
        await events.add(run.id, 1, data["type"], False, data)
        recorder = SimulationRecorder(session_factory, run.id, chat.id, project.id)
        await recorder.on_event(None, FINISHED)

    results = await ResultRepository(session).all_for_project(project.id)
    assert [item.content["simulation"] for item in results] == ["result/abc"]


async def test_a_sensitivity_without_a_simulate_gets_a_result_on_the_latest_case(
    session_factory, session, make_user, make_project, make_chat, make_run
) -> None:
    from tests.blobs import MemoryBlobStore

    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    run = await make_run(chat, owner)
    blobs = MemoryBlobStore()
    case = design_inputs.case_content()
    files = design_inputs.case_files()
    version = await CaseVersionRepository(session).save_version(
        project.id, case, "first", owner.id, files_digest(case, files)
    )
    for name, data in files.items():
        await blobs.put(f"case/{name}", data)
        await CaseFileRepository(session).add(
            project.id, version.id, name, len(data), f"case/{name}"
        )
    design = gm.Plant.from_dict(design_inputs.plant_content()).to_dict(structure=True)
    await PlantVersionRepository(session).save_version(
        project.id, design, "adopted as it was", owner.id
    )
    artifacts = RunArtifactRepository(session)
    await artifacts.save(None, chat.id, "design/v1", design)
    await artifacts.save(
        None,
        chat.id,
        "study/sens",
        {"result": {"rows": []}, "designs": {"read": ["design/v1"], "wrote": []}},
    )
    study = await StudyRepository(session).create(
        {
            "project_id": project.id,
            "kind": "sensitivity",
            "name": "sens",
            "settings": {},
            "status": "done",
            "started_by_kind": "agent",
            "started_by_name": "Assistant",
            "started_by_run_id": run.id,
            "case_version": 1,
            "plant_version": None,
        }
    )
    recorder = SimulationRecorder(session_factory, run.id, chat.id, project.id, blobs)

    await recorder.on_event(None, FINISHED)

    results = await ResultRepository(session).all_for_project(project.id)
    assert [(item.study_id, item.name, item.plant_version) for item in results] == [
        (study.id, "sens", 1)
    ]
    assert results[0].content["run"] == {"found": {"rows": []}}
    assert results[0].content["coverage"]["heating"]
