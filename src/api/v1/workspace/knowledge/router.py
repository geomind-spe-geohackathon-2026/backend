from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, status
from src.api.v1.workspace.knowledge import schemas, services
from src.core.clients.postgres.repositories.knowledge import (
    KnowledgeRepository,
    get_knowledge_repository,
)
from src.core.pagination.page import Page, PageParams
from src.core.security.access import AdminUser, CurrentUser
from src.core.uploads import read_upload

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

KnowledgeRepositoryDependency = Annotated[
    KnowledgeRepository, Depends(get_knowledge_repository)
]


@router.get("/settings", response_model=schemas.KnowledgeSettings)
async def read_settings(_user: CurrentUser) -> schemas.KnowledgeSettings:
    return services.read_settings()


@router.get("", response_model=Page[schemas.Entry])
async def list_entries(
    _user: CurrentUser,
    page: PageParams,
    repository: KnowledgeRepositoryDependency,
    section: schemas.Section = "knowledge",
    query: Annotated[str | None, Query(alias="q", max_length=200)] = None,
) -> Page:
    return await services.list_entries(section, query, page, repository)


@router.post("", response_model=schemas.Entry, status_code=status.HTTP_201_CREATED)
async def add_entry(
    payload: schemas.EntryInput,
    user: AdminUser,
    repository: KnowledgeRepositoryDependency,
) -> dict[str, Any]:
    return await services.add_entry(payload, user, repository)


@router.post("/import", response_model=schemas.ImportReport)
async def import_entries(
    file: UploadFile,
    user: AdminUser,
    repository: KnowledgeRepositoryDependency,
) -> schemas.ImportReport:
    return await services.import_entries(await read_upload(file), user, repository)


@router.get("/{section}/{entry_id}", response_model=schemas.Entry)
async def get_entry(
    section: schemas.Section,
    entry_id: str,
    _user: CurrentUser,
    repository: KnowledgeRepositoryDependency,
    project: UUID | None = None,
) -> dict[str, Any]:
    return await services.get_entry(section, entry_id, project, repository)


@router.patch("/knowledge/{entry_id}", response_model=schemas.Entry)
async def change_entry(
    entry_id: str,
    payload: schemas.EntryChange,
    user: AdminUser,
    repository: KnowledgeRepositoryDependency,
    project: UUID | None = None,
) -> dict[str, Any]:
    return await services.change_entry(entry_id, project, payload, user, repository)


@router.delete("/{section}/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    section: schemas.Section,
    entry_id: str,
    _admin: AdminUser,
    repository: KnowledgeRepositoryDependency,
    project: UUID | None = None,
) -> None:
    await services.delete_entry(section, entry_id, project, repository)
