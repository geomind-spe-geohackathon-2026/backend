from typing import Annotated
from uuid import UUID

from minio import Minio

from fastapi import APIRouter, Depends, Form, Query, UploadFile, status
from src.api.v1.workspace.documents import schemas, services
from src.core.clients.minio.client import get_minio
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.repositories.document import (
    DocumentRepository,
    get_document_repository,
)
from src.core.clients.postgres.repositories.project import (
    ProjectRepository,
    get_project_repository,
)
from src.core.pagination.page import Page, PageParams
from src.core.security.access import CurrentUser, require_project

router = APIRouter(prefix="/documents", tags=["Documents"])

DocumentRepositoryDependency = Annotated[
    DocumentRepository,
    Depends(get_document_repository),
]
MinioDependency = Annotated[Minio, Depends(get_minio)]
ProjectRepositoryDependency = Annotated[
    ProjectRepository,
    Depends(get_project_repository),
]


async def project_from_query(
    project: Annotated[UUID, Query()],
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
) -> Project:
    return await require_project(project, user, repository)


async def project_from_form(
    project: Annotated[UUID, Form()],
    user: CurrentUser,
    repository: ProjectRepositoryDependency,
) -> Project:
    return await require_project(project, user, repository)


@router.get("", response_model=Page[schemas.Document])
async def list_documents(
    project: Annotated[Project, Depends(project_from_query)],
    page: PageParams,
    repository: DocumentRepositoryDependency,
) -> Page:
    return await services.list_documents(project, page, repository)


@router.post(
    "",
    response_model=schemas.Document,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project: Annotated[Project, Depends(project_from_form)],
    file: UploadFile,
    user: CurrentUser,
    repository: DocumentRepositoryDependency,
    minio: MinioDependency,
) -> schemas.Document:
    return await services.upload_document(project, user, file, repository, minio)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: CurrentUser,
    repository: DocumentRepositoryDependency,
    projects: ProjectRepositoryDependency,
    minio: MinioDependency,
) -> None:
    await services.delete_document(document_id, user, repository, projects, minio)
