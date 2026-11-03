from pathlib import PurePosixPath
from uuid import UUID, uuid4

from fastapi import UploadFile
from src.api.v1.workspace.rag import schemas
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.rag_document import RagDocument
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.errors import ForbiddenError, ValidationFailedError
from src.core.logging.logger import get_logger
from src.core.pagination.page import Page, PageRequest, encode_cursor
from src.core.rag.errors import RagDocumentNotFoundError
from src.core.rag.extract import SUPPORTED_SUFFIXES, extract_text, is_supported
from src.core.security.access import require_project
from src.core.security.errors import ProjectNotFoundError
from src.core.uploads import read_upload

EXTRACT_TASK = "workspace.rag.extract"
PDF_MEDIA_TYPE = "application/pdf"
PLAIN_TEXT = "text/plain; charset=utf-8"
KNOWLEDGE_FOLDER = "rag/shared"

logger = get_logger(__name__)


def describe_document(document: RagDocument) -> schemas.RagDocument:
    return schemas.RagDocument(
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
    project: Project | None,
    page: PageRequest,
    repository: RagDocumentRepository,
) -> Page:
    """List a project's documents, or with no project the shared Knowledge."""
    rows = await repository.list_page(None if project is None else project.id, page)
    items = rows[: page.limit]
    last = items[-1] if len(rows) > page.limit else None
    return Page(
        items=[describe_document(document) for document in items],
        next=encode_cursor(last.created, last.id) if last else None,
    )


def list_formats() -> list[str]:
    """Return the file suffixes an upload may have."""
    return sorted(SUPPORTED_SUFFIXES)


def file_name_of(raw: str | None) -> str:
    name = PurePosixPath((raw or "").replace("\\", "/")).name
    if name in ("", ".", ".."):
        raise ValidationFailedError({"file": "File name is required"})
    return name


def require_admin_for_shared(project: Project | None, user: User) -> None:
    """Refuse a shared Knowledge change by anyone but an admin."""
    if project is None and user.role != "admin":
        raise ForbiddenError("Only an administrator changes the shared Knowledge")


def object_key_of(project: Project | None, name: str) -> str:
    folder = KNOWLEDGE_FOLDER if project is None else f"projects/{project.id}/rag"
    return f"{folder}/{uuid4()}/{name}"


async def upload_document(
    project: Project | None,
    user: User,
    file: UploadFile,
    repository: RagDocumentRepository,
    blobs: BlobStore,
) -> schemas.RagDocument:
    require_admin_for_shared(project, user)
    name = file_name_of(file.filename)
    if not is_supported(name):
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ValidationFailedError(
            {"file": f"This file type cannot be read; upload one of {supported}"}
        )
    data = await read_upload(file)
    key = object_key_of(project, name)
    owner = None if project is None else project.id
    await blobs.put(key, data)
    try:
        document = await repository.create(owner, name, len(data), key, user.id)
    except Exception:
        await blobs.delete(key)
        raise
    enqueue_extraction(document.id)
    return describe_document(document)


async def readable_document(
    document_id: UUID,
    user: User,
    repository: RagDocumentRepository,
    projects: ProjectRepository,
) -> RagDocument:
    """Return a document the user may see: a shared one, or one of their projects."""
    document = await repository.get_by_id(document_id)
    if document is None:
        raise RagDocumentNotFoundError("Document not found")
    if document.project_id is not None:
        try:
            await require_project(document.project_id, user, projects)
        except ProjectNotFoundError as error:
            raise RagDocumentNotFoundError("Document not found") from error
    return document


def shown_media_type(name: str) -> str:
    """Return how a browser may show a file: a PDF as itself, any text as plain text.

    Text formats are sent as plain text, so a file with markup never runs as a page.
    """
    return PDF_MEDIA_TYPE if name.lower().endswith(".pdf") else PLAIN_TEXT


async def read_file(
    document_id: UUID,
    user: User,
    repository: RagDocumentRepository,
    projects: ProjectRepository,
    blobs: BlobStore,
) -> tuple[bytes, str, str]:
    """Return a document's bytes, how to show them and its name."""
    document = await readable_document(document_id, user, repository, projects)
    data = await blobs.get(document.object_key)
    if data is None:
        raise RagDocumentNotFoundError("Document file is missing from storage")
    return data, shown_media_type(document.name), document.name


async def read_text(
    document_id: UUID,
    user: User,
    repository: RagDocumentRepository,
    projects: ProjectRepository,
) -> schemas.RagDocumentText:
    """Return the text the backend read from a document, as the agents search it."""
    document = await readable_document(document_id, user, repository, projects)
    return schemas.RagDocumentText(
        id=document.id,
        name=document.name,
        searchable=document.searchable,
        text=document.text,
    )


async def delete_document(
    document_id: UUID,
    user: User,
    repository: RagDocumentRepository,
    projects: ProjectRepository,
    blobs: BlobStore,
) -> None:
    document = await readable_document(document_id, user, repository, projects)
    if document.project_id is None:
        require_admin_for_shared(None, user)
    await repository.delete(document.id)
    await blobs.delete(document.object_key)


async def extract_document(
    document_id: UUID,
    repository: RagDocumentRepository,
    blobs: BlobStore,
) -> None:
    """Read a stored document and keep its text for search; safe to run twice."""
    document = await repository.get_by_id(document_id)
    if document is None:
        logger.info("RagDocument %s was deleted before extraction", document_id)
        return
    try:
        data = await blobs.get(document.object_key)
        if data is None:
            raise RagDocumentNotFoundError("RagDocument file is missing from storage")
    except Exception:
        await repository.set_text(document, None)
        raise
    await repository.set_text(document, extract_text(document.name, data))
