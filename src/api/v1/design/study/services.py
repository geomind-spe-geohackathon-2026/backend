import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.design.study import errors, schemas
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.study import ACTIVE_STUDY_STATUSES, Study
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.clients.redis.models.job import JobProgress
from src.core.clients.redis.repositories.job import JobRepository
from src.core.errors import (
    AppError,
    ConflictError,
    MissingInputsError,
    ValidationFailedError,
)
from src.core.gemini import evaluate as gemini_evaluate
from src.core.gemini import study as gemini_study
from src.core.gemini.stored import stored_files
from src.core.jobs import control
from src.core.pagination.page import Page, PageRequest, encode_cursor
from src.core.routes import RESULTS_ROUTE, STUDY_ROUTE
from src.core.security.access import require_project
from src.core.security.errors import ProjectNotFoundError

CANCELLABLE = ("queued", "running", "blocked")


@dataclass(frozen=True, slots=True)
class Stores:
    """The repositories a study touches, opened on one database session."""

    projects: ProjectRepository
    studies: StudyRepository
    results: ResultRepository
    plants: PlantVersionRepository
    cases: CaseVersionRepository
    files: CaseFileRepository
    activity: ActivityRepository

    @classmethod
    def open(cls, session: AsyncSession) -> "Stores":
        return cls(
            ProjectRepository(session),
            StudyRepository(session),
            ResultRepository(session),
            PlantVersionRepository(session),
            CaseVersionRepository(session),
            CaseFileRepository(session),
            ActivityRepository(session),
        )


@dataclass(frozen=True, slots=True)
class Inputs:
    """The plant and case versions a study runs on, and the files the case names."""

    plant: PlantVersion | None
    case: CaseVersion | None
    case_files: dict[str, bytes]


async def find_version(
    repository: PlantVersionRepository | CaseVersionRepository,
    project_id: UUID,
    number: int | None,
) -> Any | None:
    if number is None:
        return await repository.latest_version(project_id)
    return await repository.version_by_number(project_id, number)


async def gather_inputs(
    project_id: UUID,
    stores: Stores,
    blobs: BlobStore,
    plant_number: int | None = None,
    case_number: int | None = None,
) -> Inputs:
    """Read the named versions, or the latest ones, with the case's files."""
    plant = await find_version(stores.plants, project_id, plant_number)
    case = await find_version(stores.cases, project_id, case_number)
    rows = [] if case is None else await stores.files.list_for_version(case.id)
    files = await stored_files(rows, blobs)
    return Inputs(plant, case, files)


async def find_missing(
    kind: str,
    name: str,
    study_settings: dict[str, Any],
    inputs: Inputs,
) -> list[dict[str, str]]:
    """Return what the study lacks: a plant, a case, or values gemini finds unset."""
    absent = [
        {"path": label, "message": f"The project has no {label}"}
        for label, version in (("plant", inputs.plant), ("case", inputs.case))
        if version is None
    ]
    if absent:
        return absent
    return await asyncio.to_thread(
        gemini_study.missing_inputs,
        kind,
        name,
        study_settings,
        inputs.plant.content,
        inputs.case.content,
        inputs.case_files,
    )


def number_of(version: PlantVersion | CaseVersion | None) -> int | None:
    return None if version is None else version.number


def to_study(
    study: Study,
    progress: JobProgress | None,
    result_id: UUID | None,
) -> schemas.Study:
    shown = progress or JobProgress(study.progress_done, study.progress_total)
    return schemas.Study(
        id=study.id,
        project=study.project_id,
        kind=study.kind,
        name=study.name,
        settings=study.settings,
        status=study.status,
        progress=schemas.StudyProgress(done=shown.done, total=shown.total),
        started_by=schemas.StartedBy(
            kind=study.started_by_kind,
            name=study.started_by_name,
            run=study.started_by_run_id,
        ),
        case_version=study.case_version,
        plant_version=study.plant_version,
        result=result_id,
        error=study.error,
        missing=study.missing,
        created=study.created,
        ended=study.ended,
    )


async def present(
    studies: list[Study],
    stores: Stores,
    jobs: JobRepository,
) -> list[schemas.Study]:
    """Add what lives elsewhere: Redis progress of active studies and result ids."""
    done = [study.id for study in studies if study.status == "done"]
    result_ids = await stores.results.ids_by_study(done) if done else {}
    shown = []
    for study in studies:
        active = study.status in ACTIVE_STUDY_STATUSES
        progress = await jobs.progress(str(study.id)) if active else None
        shown.append(to_study(study, progress, result_ids.get(study.id)))
    return shown


async def accessible_study(study_id: UUID, user: User, stores: Stores) -> Study:
    study = await stores.studies.get_by_id(study_id)
    if study is None:
        raise errors.StudyNotFoundError("Study not found")
    try:
        await require_project(study.project_id, user, stores.projects)
    except ProjectNotFoundError as error:
        raise errors.StudyNotFoundError("Study not found") from error
    return study


def list_kinds() -> list[schemas.StudyKind]:
    return [schemas.StudyKind.model_validate(kind) for kind in gemini_study.kinds()]


async def list_studies(
    project_id: UUID,
    user: User,
    page: PageRequest,
    stores: Stores,
    jobs: JobRepository,
) -> Page:
    project = await require_project(project_id, user, stores.projects)
    rows = await stores.studies.list_page(project.id, page)
    items = rows[: page.limit]
    last = items[-1] if len(rows) > page.limit else None
    return Page(
        items=await present(items, stores, jobs),
        next=encode_cursor(last.created, last.id) if last else None,
    )


async def get_study(
    study_id: UUID,
    user: User,
    stores: Stores,
    jobs: JobRepository,
) -> schemas.Study:
    study = await accessible_study(study_id, user, stores)
    return (await present([study], stores, jobs))[0]


async def enqueue_study(
    study: Study,
    stores: Stores,
    enqueue: Callable[[UUID], str],
) -> Study:
    task_id = await asyncio.to_thread(enqueue, study.id)
    return await stores.studies.update(study, {"task_id": task_id})


async def record(
    study: Study,
    stores: Stores,
    text: str,
    route: str,
    link_id: UUID | None = None,
) -> None:
    await stores.activity.add(
        study.project_id,
        study.started_by_kind,
        study.started_by_name,
        text,
        route,
        None if link_id is None else str(link_id),
    )


async def create_study(
    payload: schemas.StudyCreate,
    user: User,
    stores: Stores,
    blobs: BlobStore,
    enqueue: Callable[[UUID], str],
) -> schemas.Study:
    project = await require_project(payload.project, user, stores.projects)
    if payload.kind not in {item["kind"] for item in gemini_study.kinds()}:
        raise ValidationFailedError({"kind": "Unknown study kind"})
    gemini_study.from_dict(payload.kind, payload.name, payload.settings)
    inputs = await gather_inputs(project.id, stores, blobs)
    missing = await find_missing(payload.kind, payload.name, payload.settings, inputs)
    study = await stores.studies.create(
        {
            "project_id": project.id,
            "kind": payload.kind,
            "name": payload.name,
            "settings": payload.settings,
            "status": "blocked" if missing else "queued",
            "started_by_kind": "user",
            "started_by_name": user.name,
            "case_version": number_of(inputs.case),
            "plant_version": number_of(inputs.plant),
            "missing": missing,
        }
    )
    if missing:
        await record(study, stores, f"Blocked study {study.name}", STUDY_ROUTE)
    else:
        study = await enqueue_study(study, stores, enqueue)
        await record(study, stores, f"Started study {study.name}", STUDY_ROUTE)
    return to_study(study, None, None)


async def start_study(
    study_id: UUID,
    user: User,
    stores: Stores,
    blobs: BlobStore,
    enqueue: Callable[[UUID], str],
) -> schemas.Study:
    study = await accessible_study(study_id, user, stores)
    if study.status != "blocked":
        raise ConflictError("Study is not blocked")
    inputs = await gather_inputs(study.project_id, stores, blobs)
    missing = await find_missing(study.kind, study.name, study.settings, inputs)
    values = {
        "missing": missing,
        "case_version": number_of(inputs.case),
        "plant_version": number_of(inputs.plant),
    }
    if missing:
        await stores.studies.update(study, values)
        raise MissingInputsError(missing)
    study = await stores.studies.update(study, {**values, "status": "queued"})
    study = await enqueue_study(study, stores, enqueue)
    await record(study, stores, f"Started study {study.name}", STUDY_ROUTE)
    return to_study(study, None, None)


async def cancel_study(
    study_id: UUID,
    user: User,
    stores: Stores,
    jobs: JobRepository,
) -> schemas.Study:
    study = await accessible_study(study_id, user, stores)
    if study.status not in CANCELLABLE:
        raise ConflictError("Study cannot be cancelled")
    study = await stores.studies.update(
        study, {"status": "cancelled", "ended": utc_now()}
    )
    await control.request_cancel(jobs, str(study.id))
    if study.task_id:
        await asyncio.to_thread(control.terminate_later, study.task_id)
    await record(study, stores, f"Cancelled study {study.name}", STUDY_ROUTE)
    return to_study(study, None, None)


def failure_of(error: AppError) -> dict[str, Any]:
    return {"code": error.code, "message": error.message, "details": error.details}


async def finish_failed(
    study: Study,
    stores: Stores,
    failure: dict[str, Any],
) -> None:
    study = await stores.studies.refresh(study)
    if study.status != "running":
        return
    values = {"status": "failed", "error": failure, "ended": utc_now()}
    study = await stores.studies.update(study, values)
    await record(study, stores, f"Study {study.name} failed", STUDY_ROUTE)


async def finish_done(
    study: Study,
    outcome: dict[str, Any],
    stores: Stores,
) -> None:
    study = await stores.studies.refresh(study)
    if study.status != "running":
        return
    parts = gemini_evaluate.summarise(outcome["report"])
    content = {
        "capacities": parts["capacities"],
        "constraints": parts["constraints"],
        "series": [],
        **outcome,
    }
    result = await stores.results.create(
        {
            "project_id": study.project_id,
            "study_id": study.id,
            "name": study.name,
            "case_version": study.case_version,
            "plant_version": study.plant_version,
            "summary": parts["summary"],
            "content": content,
        }
    )
    values = {
        "status": "done",
        "progress_done": 1,
        "progress_total": 1,
        "ended": utc_now(),
    }
    study = await stores.studies.update(study, values)
    await record(
        study, stores, f"Study {study.name} finished", RESULTS_ROUTE, result.id
    )


async def finish_cancelled(study: Study, stores: Stores) -> None:
    study = await stores.studies.refresh(study)
    if study.status == "running":
        values = {"status": "cancelled", "ended": utc_now()}
        await stores.studies.update(study, values)


async def compute(
    study: Study,
    stores: Stores,
    blobs: BlobStore,
    report: Callable[[int, int], None],
    is_cancelled: Callable[[], bool],
) -> dict[str, Any]:
    inputs = await gather_inputs(
        study.project_id, stores, blobs, study.plant_version, study.case_version
    )
    if inputs.plant is None or inputs.case is None:
        raise gemini_study.StudyRunError("The versions the study names are gone")
    return gemini_study.run(
        study.kind,
        study.name,
        study.settings,
        (inputs.plant.content, inputs.case.content, inputs.case_files),
        report,
        is_cancelled,
    )


async def run_study(
    study_id: UUID,
    stores: Stores,
    blobs: BlobStore,
    report: Callable[[str, int, int], None],
    is_cancelled: Callable[[str], bool],
) -> None:
    """Run a queued study; a study in any other state is left alone.

    gemini calls back after each trial, which reports progress and stops a cancelled
    study; trials already run are lost. An unexpected error is recorded on the study
    and raised again.
    """
    study = await stores.studies.get_by_id(study_id)
    if study is None or study.status != "queued":
        return
    study = await stores.studies.update(
        study, {"status": "running", "started": utc_now()}
    )
    job = str(study.id)
    report(job, 0, 1)

    def trial(done: int, total: int) -> None:
        report(job, done, total)

    try:
        outcome = await compute(study, stores, blobs, trial, lambda: is_cancelled(job))
    except gemini_study.StudyCancelledError:
        await finish_cancelled(study, stores)
        return
    except AppError as error:
        await finish_failed(study, stores, failure_of(error))
        return
    except Exception as error:
        await finish_failed(study, stores, failure_of(AppError(str(error))))
        raise
    await finish_done(study, outcome, stores)
