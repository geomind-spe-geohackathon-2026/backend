import asyncio
import json
import re
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePosixPath
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from pydantic import ValidationError

from fastapi import UploadFile
from src.api.v1.workspace.projects import schemas
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.progress import (
    ProgressRepository,
    ProjectFacts,
)
from src.core.clients.postgres.repositories.project import (
    ImportedCase,
    ImportedCaseFile,
    ImportedVersion,
    ProjectRepository,
)
from src.core.errors import ValidationFailedError
from src.core.gemini.errors import PlantInvalidError
from src.core.gemini.plant import validate_content
from src.core.gemini.stored import stored_files
from src.core.pagination.page import Page, PageRequest, encode_cursor
from src.core.progress.states import build_progress
from src.core.settings import settings

EXPORT_FORMAT = 1
PROJECT_FILE = "project.json"
PLANT_FILE = re.compile(r"plant/([1-9][0-9]*)\.json")
CASE_FILE = re.compile(r"case/([1-9][0-9]*)\.json")
CASE_ATTACHMENT = re.compile(r"case/files/([1-9][0-9]*)/([^/]+)")
WINDOWS_DRIVE = re.compile(r"[A-Za-z]:")
ARCHIVE_ERRORS = (BadZipFile, EOFError, NotImplementedError, RuntimeError, zlib.error)


@dataclass(frozen=True, slots=True)
class CaseArchive:
    version: CaseVersion
    files: dict[str, bytes]


@dataclass(frozen=True, slots=True)
class ParsedCase:
    number: int
    note: str
    created: datetime
    content: dict
    files: dict[str, bytes]


def describe_project(project: Project, facts: ProjectFacts) -> schemas.Project:
    return schemas.Project(
        id=project.id,
        name=project.name,
        owner=schemas.Owner.model_validate(project.owner),
        plant_version=project.plant_version,
        case_version=facts.case_version,
        created=project.created,
        updated=project.updated,
        progress=build_progress(facts),
    )


async def describe_one(
    project: Project,
    progress: ProgressRepository,
) -> schemas.Project:
    facts = await progress.facts([project.id])
    return describe_project(project, facts[project.id])


async def list_projects(
    user: User,
    page: PageRequest,
    search: str | None,
    repository: ProjectRepository,
    progress: ProgressRepository,
) -> Page:
    owner_id = None if user.role == "admin" else user.id
    rows = await repository.list_page(page, owner_id, search)
    items = rows[: page.limit]
    facts = await progress.facts([project.id for project in items])
    last = items[-1] if len(rows) > page.limit else None
    return Page(
        items=[describe_project(project, facts[project.id]) for project in items],
        next=encode_cursor(last.created, last.id) if last else None,
    )


async def create_project(
    payload: schemas.ProjectCreate,
    user: User,
    repository: ProjectRepository,
    progress: ProgressRepository,
) -> schemas.Project:
    project = await repository.create(payload.name, user.id)
    return await describe_one(project, progress)


async def get_project(
    project: Project,
    progress: ProgressRepository,
) -> schemas.Project:
    return await describe_one(project, progress)


async def rename_project(
    project: Project,
    payload: schemas.ProjectUpdate,
    repository: ProjectRepository,
    progress: ProgressRepository,
) -> schemas.Project:
    renamed = await repository.rename(project, payload.name)
    return await describe_one(renamed, progress)


async def delete_project(project: Project, repository: ProjectRepository) -> None:
    await repository.delete(project.id)


def write_archive(
    project: Project,
    versions: list[PlantVersion],
    cases: list[CaseArchive],
) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        project_file = {
            "format": EXPORT_FORMAT,
            "name": project.name,
            "exported": datetime.now(UTC).isoformat(),
        }
        archive.writestr(PROJECT_FILE, json.dumps(project_file))
        for version in versions:
            archive.writestr(f"plant/{version.number}.json", version_json(version))
        for case in cases:
            number = case.version.number
            archive.writestr(f"case/{number}.json", version_json(case.version))
            for name, data in case.files.items():
                archive.writestr(f"case/files/{number}/{name}", data)
    return buffer.getvalue()


def version_json(version: PlantVersion | CaseVersion) -> str:
    return json.dumps(
        {
            "number": version.number,
            "note": version.note,
            "created": version.created.isoformat(),
            "content": version.content,
        }
    )


async def export_project(
    project: Project,
    plants: PlantVersionRepository,
    cases: CaseVersionRepository,
    files: CaseFileRepository,
    blobs: BlobStore,
) -> bytes:
    case_archives = []
    for version in await cases.all_versions(project.id):
        rows = await files.list_for_version(version.id)
        data = await stored_files(rows, blobs)
        case_archives.append(CaseArchive(version, data))
    versions = await plants.all_versions(project.id)
    return await asyncio.to_thread(write_archive, project, versions, case_archives)


def refuse_file(message: str) -> ValidationFailedError:
    return ValidationFailedError({"file": message})


def is_unsafe_path(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return path.is_absolute() or ".." in path.parts or bool(WINDOWS_DRIVE.match(name))


def check_members(members: list[ZipInfo]) -> None:
    """Refuse an archive by its paths and unpacked size, before reading any file."""
    if any(is_unsafe_path(member.filename) for member in members):
        raise refuse_file("Archive contains an unsafe path")
    if sum(member.file_size for member in members) > settings.PROJECT_IMPORT_MAX_BYTES:
        raise refuse_file("Archive is too large")


def read_project_file(archive: ZipFile) -> schemas.ProjectFile:
    if PROJECT_FILE not in archive.namelist():
        raise refuse_file(f"Archive has no {PROJECT_FILE}")
    try:
        return schemas.ProjectFile.model_validate_json(archive.read(PROJECT_FILE))
    except ValidationError as error:
        raise refuse_file(f"{PROJECT_FILE} is not valid") from error


def read_version(name: str, number: int, data: bytes) -> ImportedVersion:
    """Check one version; every failure is plant_invalid and names the file."""
    try:
        stored = schemas.VersionFile.model_validate_json(data)
        if stored.number != number:
            raise PlantInvalidError(
                "Plant is invalid",
                details={"message": f"Version number is not {number}"},
            )
        content = validate_content(stored.content)
    except ValidationError as error:
        details = {"message": str(error.errors()[0]["msg"]), "file": name}
        raise PlantInvalidError("Plant is invalid", details=details) from error
    except PlantInvalidError as error:
        details = {**error.details, "file": name}
        raise PlantInvalidError(error.message, details=details) from error
    return ImportedVersion(number, stored.note, stored.created, content)


def read_case(name: str, number: int, data: bytes) -> ParsedCase:
    try:
        stored = schemas.CaseVersionFile.model_validate_json(data)
    except ValidationError as error:
        raise refuse_file(f"{name} is not valid") from error
    if stored.number != number:
        raise refuse_file(f"{name} has a different version number")
    return ParsedCase(number, stored.note, stored.created, stored.content, {})


def read_cases(archive: ZipFile) -> list[ParsedCase]:
    cases = {
        int(match[1]): read_case(name, int(match[1]), archive.read(name))
        for name in archive.namelist()
        if (match := CASE_FILE.fullmatch(name))
    }
    for name in archive.namelist():
        match = CASE_ATTACHMENT.fullmatch(name)
        if match is None:
            continue
        if int(match[1]) not in cases:
            raise refuse_file(f"{name} belongs to a case version that is missing")
        cases[int(match[1])].files[match[2]] = archive.read(name)
    return sorted(cases.values(), key=lambda case: case.number)


def read_archive(
    upload: bytes,
) -> tuple[str, list[ImportedVersion], list[ParsedCase]]:
    """Return the name, plant versions and case versions of an exported project."""
    try:
        with ZipFile(BytesIO(upload)) as archive:
            check_members(archive.infolist())
            project_file = read_project_file(archive)
            versions = [
                read_version(name, int(match[1]), archive.read(name))
                for name in archive.namelist()
                if (match := PLANT_FILE.fullmatch(name))
            ]
            cases = read_cases(archive)
    except ARCHIVE_ERRORS as error:
        raise refuse_file("File is not a valid zip archive") from error
    versions.sort(key=lambda version: version.number)
    return project_file.name, versions, cases


async def store_cases(
    blobs: BlobStore,
    project_id: UUID,
    parsed: list[ParsedCase],
) -> list[ImportedCase]:
    cases = []
    for case in parsed:
        files = []
        for name, data in case.files.items():
            key = f"projects/{project_id}/case/{case.number}/{name}"
            await blobs.put(key, data)
            files.append(ImportedCaseFile(name, len(data), key))
        cases.append(
            ImportedCase(case.number, case.note, case.created, case.content, files)
        )
    return cases


async def remove_cases(blobs: BlobStore, cases: list[ImportedCase]) -> None:
    for case in cases:
        for file in case.files:
            await blobs.delete(file.object_key)


async def import_project(
    file: UploadFile,
    user: User,
    repository: ProjectRepository,
    progress: ProgressRepository,
    blobs: BlobStore,
) -> schemas.Project:
    upload = await file.read(settings.PROJECT_IMPORT_MAX_BYTES + 1)
    if len(upload) > settings.PROJECT_IMPORT_MAX_BYTES:
        raise refuse_file("Archive is too large")
    name, plants, parsed = await asyncio.to_thread(read_archive, upload)
    project_id = uuid4()
    cases = await store_cases(blobs, project_id, parsed)
    try:
        project = await repository.create_with_versions(
            project_id, name, user.id, plants, cases
        )
    except Exception:
        await remove_cases(blobs, cases)
        raise
    return await describe_one(project, progress)
