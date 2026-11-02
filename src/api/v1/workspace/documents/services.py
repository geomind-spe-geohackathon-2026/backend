from pathlib import PurePosixPath
from uuid import UUID, uuid4

from fastapi import UploadFile
from src.api.v1.workspace.documents import schemas
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.document import Document
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.document import DocumentRepository
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.documents.errors import DocumentNotFoundError
from src.core.documents.extract import SUPPORTED_SUFFIXES, extract_text, is_supported
from src.core.errors import ValidationFailedError
from src.core.logging.logger import get_logger
from src.core.pagination.page import Page, PageRequest, encode_cursor
from src.core.security.access import require_project
from src.core.security.errors import ProjectNotFoundError
from src.core.uploads import read_upload

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
    blobs: BlobStore,
) -> schemas.Document:
    name = file_name_of(file.filename)
    if not is_supported(name):
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ValidationFailedError(
            {"file": f"This file type cannot be read; upload one of {supported}"}
        )
    data = await read_upload(file)
    key = f"projects/{project.id}/documents/{uuid4()}/{name}"
    await blobs.put(key, data)
    try:
        document = await repository.create(project.id, name, len(data), key, user.id)
    except Exception:
        await blobs.delete(key)
        raise
    enqueue_extraction(document.id)
    return describe_document(document)


async def delete_document(
    document_id: UUID,
    user: User,
    repository: DocumentRepository,
    projects: ProjectRepository,
    blobs: BlobStore,
) -> None:
    document = await repository.get_by_id(document_id)
    if document is None:
        raise DocumentNotFoundError("Document not found")
    try:
        await require_project(document.project_id, user, projects)
    except ProjectNotFoundError as error:
        raise DocumentNotFoundError("Document not found") from error
    await repository.delete(document.id)
    await blobs.delete(document.object_key)


async def extract_document(
    document_id: UUID,
    repository: DocumentRepository,
    blobs: BlobStore,
) -> None:
    """Read a stored document and keep its text for search; safe to run twice."""
    document = await repository.get_by_id(document_id)
    if document is None:
        logger.info("Document %s was deleted before extraction", document_id)
        return
    try:
        data = await blobs.get(document.object_key)
        if data is None:
            raise DocumentNotFoundError("Document file is missing from storage")
    except Exception:
        await repository.set_text(document, None)
        raise
    await repository.set_text(document, extract_text(document.name, data))
