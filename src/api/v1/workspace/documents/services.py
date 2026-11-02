import asyncio
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from minio import Minio

from fastapi import UploadFile
from src.api.v1.workspace.documents import schemas
from src.core.clients.postgres.models.document import Document
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.document import DocumentRepository
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.documents.errors import DocumentNotFoundError
from src.core.documents.extract import extract_text
from src.core.documents.storage import read_object, remove_object, store_object
from src.core.errors import ValidationFailedError
from src.core.logging.logger import get_logger
from src.core.pagination.page import Page, PageRequest, encode_cursor
from src.core.security.access import require_project
from src.core.security.errors import ProjectNotFoundError
from src.core.settings import settings

EXTRACT_TASK = "workspace.documents.extract"

logger = get_logger(__name__)


def describe_document(document: Document) -> schemas.Document:
    return schemas.Document(
        id=document.id,
        project=document.project_id,
        name=document.name,
        size=document.size,
        searchable=document.searchable,
        created=document.created,
    )


def enqueue_extraction(document_id: UUID) -> None:
    """Send the extraction to the workers.

    The Celery app is imported here because it imports every feature's tasks.
    """
    from src.celery import app

    app.send_task(EXTRACT_TASK, args=[str(document_id)])


async def list_documents(
    project: Project,
    page: PageRequest,
    repository: DocumentRepository,
) -> Page:
    rows = await repository.list_page(project.id, page)
    items = rows[: page.limit]
    last = items[-1] if len(rows) > page.limit else None
    return Page(
        items=[describe_document(document) for document in items],
        next=encode_cursor(last.created, last.id) if last else None,
    )


def file_name_of(raw: str | None) -> str:
    name = PurePosixPath((raw or "").replace("\\", "/")).name
    if name in ("", ".", ".."):
        raise ValidationFailedError({"file": "File name is required"})
    return name


async def upload_document(
    project: Project,
    user: User,
    file: UploadFile,
    repository: DocumentRepository,
    minio: Minio,
) -> schemas.Document:
    name = file_name_of(file.filename)
    data = await file.read(settings.PROJECT_IMPORT_MAX_BYTES + 1)
    if len(data) > settings.PROJECT_IMPORT_MAX_BYTES:
        raise ValidationFailedError({"file": "File is too large"})
    key = f"projects/{project.id}/documents/{uuid4()}/{name}"
    await asyncio.to_thread(store_object, minio, key, data)
    try:
        document = await repository.create(project.id, name, len(data), key, user.id)
    except Exception:
        await asyncio.to_thread(remove_object, minio, key)
        raise
    enqueue_extraction(document.id)
    return describe_document(document)


async def delete_document(
    document_id: UUID,
    user: User,
    repository: DocumentRepository,
    projects: ProjectRepository,
    minio: Minio,
) -> None:
    document = await repository.get_by_id(document_id)
    if document is None:
        raise DocumentNotFoundError("Document not found")
    try:
        await require_project(document.project_id, user, projects)
    except ProjectNotFoundError as error:
        raise DocumentNotFoundError("Document not found") from error
    await repository.delete(document.id)
    await asyncio.to_thread(remove_object, minio, document.object_key)


async def extract_document(
    document_id: UUID,
    repository: DocumentRepository,
    minio: Minio,
) -> None:
    """Read a stored document and keep its text for search; safe to run twice."""
    document = await repository.get_by_id(document_id)
    if document is None:
        logger.info("Document %s was deleted before extraction", document_id)
        return
    try:
        data = await asyncio.to_thread(read_object, minio, document.object_key)
    except Exception:
        await repository.set_text(document, None)
        raise
    await repository.set_text(document, extract_text(document.name, data))
