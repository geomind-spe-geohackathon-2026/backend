import asyncio
import hashlib
from pathlib import PurePosixPath
from typing import Any

from src.api.v1.design.case import schemas
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
from src.core.clients.postgres.repositories.version import content_digest
from src.core.errors import CaseInvalidError, ValidationFailedError
from src.core.gemini import case
from src.core.gemini.errors import CaseFileNotFoundError, CaseNotFoundError
from src.core.gemini.stored import stored_files
from src.core.pagination.page import Page
from src.core.versioning import (
    Version,
    check_base,
    describe_versions,
    latest_version,
)


def object_key(project_id: Any, data: bytes) -> str:
    return f"case/{project_id}/{hashlib.sha256(data).hexdigest()}"


def check_name(name: str) -> None:
    """Refuse a file name that is empty, absolute or climbs out of the case folder."""
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts:
        raise ValidationFailedError({"name": "Name must be a relative path"})


def files_digest(content: dict[str, Any], files: dict[str, bytes]) -> str:
    """Hash a case document together with the bytes of its files."""
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    return content_digest({"content": content, "files": hashes})


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


def check_case(content: dict[str, Any]) -> schemas.CaseProblems:
    """Return gemini's missing values and problems for a case document."""
    missing, problems = case.validate(content, None)
    return schemas.CaseProblems(missing=missing, problems=problems)


async def save_version(
    project: Project,
    user: User,
    content: dict[str, Any],
    note: str,
    files: dict[str, bytes],
    repository: CaseVersionRepository,
) -> CaseVersion:
    """Check the case with its files, then save it as the next version."""
    _, problems = await asyncio.to_thread(case.validate, content, files)
    if problems:
        raise CaseInvalidError(problems)
    return await repository.save_version(
        project.id, content, note, user.id, files_digest(content, files)
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
        "design/case",
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
        built = case.ensure_complete(version.content, files)
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
