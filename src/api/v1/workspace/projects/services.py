import asyncio
import json
import re
import zlib
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from pydantic import ValidationError

from fastapi import UploadFile
from src.api.v1.workspace.projects import schemas
from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.project import (
    ImportedVersion,
    ProjectRepository,
)
from src.core.errors import ValidationFailedError
from src.core.gemini.errors import PlantInvalidError
from src.core.gemini.plant import validate_content
from src.core.pagination.page import Page, PageRequest, build_page
from src.core.settings import settings

EXPORT_FORMAT = 1
PROJECT_FILE = "project.json"
PLANT_FILE = re.compile(r"plant/([1-9][0-9]*)\.json")
WINDOWS_DRIVE = re.compile(r"[A-Za-z]:")
ARCHIVE_ERRORS = (BadZipFile, EOFError, NotImplementedError, RuntimeError, zlib.error)


async def list_projects(
    user: User,
    page: PageRequest,
    repository: ProjectRepository,
) -> Page:
    owner_id = None if user.role == "admin" else user.id
    rows = await repository.list_page(page, owner_id)
    return build_page(rows, page, schemas.ProjectResponse)


async def create_project(
    payload: schemas.ProjectCreate,
    user: User,
    repository: ProjectRepository,
) -> Project:
    return await repository.create(payload.name, user.id)


async def delete_project(project: Project, repository: ProjectRepository) -> None:
    await repository.delete(project.id)


def write_archive(project: Project, versions: list[PlantVersion]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        project_file = {
            "format": EXPORT_FORMAT,
            "name": project.name,
            "exported": datetime.now(UTC).isoformat(),
        }
        archive.writestr(PROJECT_FILE, json.dumps(project_file))
        for version in versions:
            version_file = {
                "number": version.number,
                "note": version.note,
                "created": version.created.isoformat(),
                "content": version.content,
            }
            archive.writestr(f"plant/{version.number}.json", json.dumps(version_file))
    return buffer.getvalue()


async def export_project(
    project: Project,
    repository: PlantVersionRepository,
) -> bytes:
    return write_archive(project, await repository.all_versions(project.id))


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


def read_archive(upload: bytes) -> tuple[str, list[ImportedVersion]]:
    """Return the name and versions of an exported project, all of them checked."""
    try:
        with ZipFile(BytesIO(upload)) as archive:
            check_members(archive.infolist())
            project_file = read_project_file(archive)
            versions = [
                read_version(name, int(match[1]), archive.read(name))
                for name in archive.namelist()
                if (match := PLANT_FILE.fullmatch(name))
            ]
    except ARCHIVE_ERRORS as error:
        raise refuse_file("File is not a valid zip archive") from error
    return project_file.name, sorted(versions, key=lambda version: version.number)


async def import_project(
    file: UploadFile,
    user: User,
    repository: ProjectRepository,
) -> Project:
    upload = await file.read(settings.PROJECT_IMPORT_MAX_BYTES + 1)
    if len(upload) > settings.PROJECT_IMPORT_MAX_BYTES:
        raise refuse_file("Archive is too large")
    name, versions = await asyncio.to_thread(read_archive, upload)
    return await repository.create_with_versions(name, user.id, versions)
