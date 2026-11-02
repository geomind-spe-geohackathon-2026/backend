from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.progress import (
    ProgressRepository,
    ProjectFacts,
)
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.progress.states import build_progress


def states(facts: ProjectFacts) -> list[str]:
    progress = build_progress(facts)
    return [
        progress.case.state,
        progress.plant.state,
        progress.study.state,
        progress.results.state,
        progress.report.state,
    ]


def test_empty_project() -> None:
    assert states(ProjectFacts()) == ["empty"] * 5


def test_versions_and_results() -> None:
    facts = ProjectFacts(case_version=2, plant_version=1, results=3)

    progress = build_progress(facts)

    assert states(facts) == ["ready", "ready", "empty", "done", "ready"]
    assert progress.case.label == "Version 2"
    assert progress.results.label == "3 results"


def test_running_beats_done_and_blocked() -> None:
    running = ProjectFacts(studies={"running": 1, "done": 2, "blocked": 1})
    done = ProjectFacts(studies={"done": 2, "blocked": 1})
    blocked = ProjectFacts(studies={"blocked": 1, "failed": 2})

    assert build_progress(running).study.state == "running"
    assert build_progress(done).study.state == "done"
    assert build_progress(blocked).study.state == "incomplete"


def test_report_done_once_exported() -> None:
    assert build_progress(ProjectFacts(reported=True)).report.state == "done"


async def test_facts_are_read_from_the_tables(
    session,
    make_user,
    make_project,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    other = await make_project(owner)
    await CaseVersionRepository(session).save_version(
        project.id, {"a": 1}, "", owner.id
    )
    await StudyRepository(session).create(
        {
            "project_id": project.id,
            "kind": "size",
            "name": "S",
            "settings": {},
            "status": "queued",
            "started_by_kind": "user",
            "started_by_name": "x",
        }
    )
    await ResultRepository(session).create(
        {"project_id": project.id, "name": "R", "summary": {}, "content": {}}
    )
    await ActivityRepository(session).add(
        project.id, "user", "x", "t", "design/report", None
    )

    facts = await ProgressRepository(session).facts([project.id, other.id])

    assert facts[project.id] == ProjectFacts(
        case_version=1,
        studies={"queued": 1},
        results=1,
        reported=True,
    )
    assert facts[other.id] == ProjectFacts()
