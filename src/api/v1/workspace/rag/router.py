from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Response, UploadFile, status
from src.api.v1.workspace.rag import schemas, services
from src.core.clients.minio.blobs import BlobStoreDependency
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.repositories.project import (
    ProjectRepository,
    get_project_repository,
)
from src.core.clients.postgres.repositories.rag_document import (
    RagDocumentRepository,
    get_rag_document_repository,
)
from src.core.pagination.page import Page, PageParams
from src.core.security.access import CurrentUser, require_project

router = APIRouter(prefix="/rag", tags=["RAG"])

RagDocumentRepositoryDependency = Annotated[
    RagDocumentRepository,
    Depends(get_rag_document_repository),
]
ProjectRepositoryDependency = Annotated[
    ProjectRepository,
    Depends(get_project_repository),
]


async def project_from_form(
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
    project: Annotated[UUID | None, Form()] = None,
) -> Project | None:
    """Return the named project, or ``None`` for the shared Knowledge."""
    return None if project is None else await require_project(project, user, repository)


async def optional_project(
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
    project: Annotated[UUID | None, Query()] = None,
) -> Project | None:
    return None if project is None else await require_project(project, user, repository)


@router.get("/formats", response_model=list[str])
async def list_formats(_user: CurrentUser) -> list[str]:
    return services.list_formats()


@router.get("", response_model=Page[schemas.RagDocument])
async def list_documents(
    project: Annotated[Project | None, Depends(optional_project)],
    page: PageParams,
    repository: RagDocumentRepositoryDependency,
) -> Page:
    return await services.list_documents(project, page, repository)


@router.post(
    "",
    response_model=schemas.RagDocument,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project: Annotated[Project | None, Depends(project_from_form)],
    file: UploadFile,
    user: CurrentUser,
    repository: RagDocumentRepositoryDependency,
    blobs: BlobStoreDependency,
) -> schemas.RagDocument:
    return await services.upload_document(project, user, file, repository, blobs)


@router.get(
    "/{document_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}, "text/plain": {}}}},
)
async def read_file(
    document_id: UUID,
    user: CurrentUser,
    repository: RagDocumentRepositoryDependency,
    projects: ProjectRepositoryDependency,
    blobs: BlobStoreDependency,
) -> Response:
    data, media_type, name = await services.read_file(
        document_id, user, repository, projects, blobs
    )
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{document_id}/text", response_model=schemas.RagDocumentText)
async def read_text(
    document_id: UUID,
    user: CurrentUser,
    repository: RagDocumentRepositoryDependency,
    projects: ProjectRepositoryDependency,
) -> schemas.RagDocumentText:
    return await services.read_text(document_id, user, repository, projects)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: CurrentUser,
    repository: RagDocumentRepositoryDependency,
    projects: ProjectRepositoryDependency,
    blobs: BlobStoreDependency,
) -> None:
    await services.delete_document(document_id, user, repository, projects, blobs)
