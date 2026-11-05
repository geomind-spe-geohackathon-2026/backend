import asyncio
from pathlib import PurePosixPath
from typing import Any

from src.api.v1.design.case import schemas
from src.core.case_versions import files_digest, object_key
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.case_file import CaseFile
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.errors import CaseInvalidError, ValidationFailedError
from src.core.gemini import case, plant
from src.core.gemini.errors import CaseFileNotFoundError, CaseNotFoundError
from src.core.gemini.stored import stored_files
from src.core.pagination.page import Page
from src.core.routes import CASE_ROUTE
from src.core.versioning import (
    Version,
    check_base,
    describe_versions,
    latest_version,
)


def check_name(name: str) -> None:
    """Refuse a file name that is empty, absolute or climbs out of the case folder."""
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts:
        raise ValidationFailedError({"name": "Name must be a relative path"})


TIME_NAMES = ("date", "datetime", "timestamp")
"""First-column names of a series CSV that mean its time column (QA-032)."""


def with_time_column(name: str, data: bytes) -> bytes:
    """Return a CSV whose first column is named ``date``/``datetime``/``timestamp`` as ``time``.

    gemini reads a series only when the first column is named ``time``; the competition's own
    demand files start with ``date`` and were refused on the Case page, with no way to say which
    column is the time (QA-032). Other files are returned as they are.
    """
    if not name.lower().endswith(".csv"):
        return data
    text = data.decode("utf-8-sig", errors="strict") if data else ""
    head, newline, rest = text.partition("\n")
    first, comma, others = head.partition(",")
    if not comma or first.strip().strip('"').lower() not in TIME_NAMES:
        return data
    return ("time," + others + newline + rest).encode()


async def build_case(
    version: CaseVersion,
    files_repository: CaseFileRepository,
    blobs: BlobStore,
) -> schemas.Case:
    rows = await files_repository.list_for_version(version.id)
    files = await stored_files(rows, blobs)
    missing, problems = await asyncio.to_thread(case.validate, version.content, files)
    return schemas.Case(
        project=version.project_id,
        version=version.number,
        content=version.content,
        files=[schemas.CaseFile(name=row.name, size=row.size) for row in rows],
        missing=missing,
        problems=problems,
    )


async def get_case(
    project: Project,
    repository: CaseVersionRepository,
    files_repository: CaseFileRepository,
    blobs: BlobStore,
) -> schemas.Case:
    """Return the latest case of a project with what gemini finds missing."""
    version = await latest_version(repository, project.id, CaseNotFoundError)
    return await build_case(version, files_repository, blobs)


async def saved_files(
    project: Project,
    repository: CaseVersionRepository,
    files: CaseFileRepository,
    blobs: BlobStore,
) -> dict[str, bytes] | None:
    """Return the files of the project's latest case, or ``None`` without a case."""
    latest = await repository.latest_version(project.id)
    if latest is None:
        return None
    return await stored_files(await files.list_for_version(latest.id), blobs)


def check_case(
    content: dict[str, Any],
    files: dict[str, bytes] | None = None,
    plant_content: dict[str, Any] | None = None,
) -> schemas.CaseProblems:
    """Return gemini's missing values and problems, and what the plant still needs."""
    missing, problems = case.validate(content, files)
    built = case.build(content, files) if not missing and not problems else None
    needs = []
    if plant_content is not None and built is not None:
        needs = plant.case_needs(plant_content, built)
    return schemas.CaseProblems(
        missing=missing,
        problems=problems,
        plant_missing=needs,
        warnings=[
            {"path": item["path"], "message": item["message"]}
            for item in case.warnings_of(content, files)
        ],
        has_plant=plant_content is not None,
    )


async def save_version(
    project: Project,
    user: User,
    content: dict[str, Any],
    note: str,
    files: dict[str, bytes],
    repository: CaseVersionRepository,
) -> CaseVersion:
    """Check the case with its files, then save it as the next version."""
    missing, problems = await asyncio.to_thread(case.validate, content, files)
    if problems:
        raise CaseInvalidError(problems)
    return await repository.save_version(
        project.id,
        content,
        note,
        user.id,
        files_digest(content, files),
        {"missing": len(missing)},
    )


async def keep_files(
    version: CaseVersion,
    rows: list[CaseFile],
    files_repository: CaseFileRepository,
) -> None:
    for row in rows:
        await files_repository.add(
            version.project_id, version.id, row.name, row.size, row.object_key
        )


async def record(
    project: Project,
    user: User,
    version: CaseVersion,
    activity: ActivityRepository,
) -> None:
    await activity.add(
        project.id,
        "user",
        user.name,
        f"Saved case version {version.number}",
        CASE_ROUTE,
        str(version.number),
    )


async def save_case(
    project: Project,
    payload: schemas.CaseCreate,
    user: User,
    repository: CaseVersionRepository,
    files_repository: CaseFileRepository,
    activity: ActivityRepository,
    blobs: BlobStore,
) -> schemas.Case:
    """Save the next case version; it keeps the files of the latest one."""
    latest = await repository.latest_version(project.id)
    check_base(latest, payload.base)
    rows = await files_repository.list_for_version(latest.id) if latest else []
    files = await stored_files(rows, blobs)
    version = await save_version(
        project, user, payload.content, payload.note, files, repository
    )
    await keep_files(version, rows, files_repository)
    await record(project, user, version, activity)
    return await build_case(version, files_repository, blobs)


async def get_version(
    project: Project,
    number: int,
    repository: CaseVersionRepository,
    files_repository: CaseFileRepository,
    blobs: BlobStore,
) -> schemas.Case:
    """Return one case version with its files and what gemini finds missing (QA-110)."""
    version = await repository.version_by_number(project.id, number)
    if version is None:
        raise CaseNotFoundError("Case version not found")
    return await build_case(version, files_repository, blobs)


async def restore_version(
    project: Project,
    number: int,
    base: int | None,
    user: User,
    repository: CaseVersionRepository,
    files_repository: CaseFileRepository,
    activity: ActivityRepository,
    blobs: BlobStore,
) -> schemas.Case:
    """Save an older case version, content and files, as the next version (QA-110)."""
    latest = await repository.latest_version(project.id)
    check_base(latest, base)
    older = await repository.version_by_number(project.id, number)
    if older is None:
        raise CaseNotFoundError("Case version not found")
    rows = await files_repository.list_for_version(older.id)
    files = await stored_files(rows, blobs)
    version = await save_version(
        project, user, older.content, f"Restored version {number}", files, repository
    )
    await keep_files(version, rows, files_repository)
    await record(project, user, version, activity)
    return await build_case(version, files_repository, blobs)


async def add_file(
    project: Project,
    base: int | None,
    name: str,
    data: bytes,
    user: User,
    repository: CaseVersionRepository,
    files_repository: CaseFileRepository,
    activity: ActivityRepository,
    blobs: BlobStore,
) -> schemas.Case:
    """Save a new case version that holds the file, replacing one of the same name."""
    check_name(name)
    try:
        data = with_time_column(name, data)
    except UnicodeDecodeError:
        pass
    latest = await latest_version(repository, project.id, CaseNotFoundError)
    check_base(latest, base)
    rows = await files_repository.list_for_version(latest.id)
    kept = [row for row in rows if row.name != name]
    files = await stored_files(kept, blobs) | {name: data}
    key = object_key(project.id, data)
    await blobs.put(key, data)
    version = await save_version(
        project, user, latest.content, f"File {name}", files, repository
    )
    await keep_files(version, kept, files_repository)
    await files_repository.add(project.id, version.id, name, len(data), key)
    await record(project, user, version, activity)
    return await build_case(version, files_repository, blobs)


async def remove_file(
    project: Project,
    base: int | None,
    name: str,
    user: User,
    repository: CaseVersionRepository,
    files_repository: CaseFileRepository,
    activity: ActivityRepository,
    blobs: BlobStore,
) -> schemas.Case:
    """Save a new case version without a file the case no longer uses."""
    latest = await latest_version(repository, project.id, CaseNotFoundError)
    check_base(latest, base)
    rows = await files_repository.list_for_version(latest.id)
    if not any(row.name == name for row in rows):
        raise CaseFileNotFoundError("File not found")
    kept = [row for row in rows if row.name != name]
    files = await stored_files(kept, blobs)
    version = await save_version(
        project, user, latest.content, f"Removed file {name}", files, repository
    )
    await keep_files(version, kept, files_repository)
    await record(project, user, version, activity)
    return await build_case(version, files_repository, blobs)


async def get_file(
    project: Project,
    name: str,
    number: int | None,
    repository: CaseVersionRepository,
    files_repository: CaseFileRepository,
    blobs: BlobStore,
) -> bytes:
    """Return a file of the latest case version, or of the numbered one."""
    if number is None:
        version = await latest_version(repository, project.id, CaseNotFoundError)
    else:
        version = await repository.version_by_number(project.id, number)
    if version is None:
        raise CaseNotFoundError("Case version not found")
    row = await files_repository.get(version.id, name)
    data = await blobs.get(row.object_key) if row else None
    if data is None:
        raise CaseFileNotFoundError(f"File {name} not found")
    return data


async def get_series(
    project: Project,
    repository: CaseVersionRepository,
    files_repository: CaseFileRepository,
    blobs: BlobStore,
) -> schemas.SeriesList:
    """Read the time series of the latest case through gemini."""
    version = await latest_version(repository, project.id, CaseNotFoundError)
    rows = await files_repository.list_for_version(version.id)
    files = await stored_files(rows, blobs)

    def read() -> list[dict[str, Any]]:
        built = case.series_case(version.content, files)
        return case.series(built, version.content)

    return schemas.SeriesList(series=await asyncio.to_thread(read))


async def list_versions(
    project: Project,
    repository: CaseVersionRepository,
    users: UserRepository,
) -> Page[Version]:
    """List the case versions of a project, newest first."""
    rows = await repository.list_versions(project.id)
    versions = await describe_versions(rows, users)
    return Page(items=versions[::-1], next=None)
