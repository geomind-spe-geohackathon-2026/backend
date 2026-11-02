from typing import Annotated
from uuid import UUID

from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, status
from src.api.v1.design.study import schemas, services, tasks
from src.core.clients.minio.client import get_minio
from src.core.clients.postgres.client import get_db
from src.core.clients.redis.repositories.job import JobRepository, get_job_repository
from src.core.pagination.page import Page, PageParams
from src.core.security.access import CurrentUser

router = APIRouter(prefix="/study", tags=["Study"])


def get_stores(session: Annotated[AsyncSession, Depends(get_db)]) -> services.Stores:
    return services.Stores.open(session)


StoresDependency = Annotated[services.Stores, Depends(get_stores)]
JobsDependency = Annotated[JobRepository, Depends(get_job_repository)]
MinioDependency = Annotated[Minio, Depends(get_minio)]


@router.get("/kinds", response_model=list[schemas.StudyKind])
async def list_kinds(_user: CurrentUser) -> list[schemas.StudyKind]:
    return services.list_kinds()


@router.get("", response_model=Page[schemas.Study])
async def list_studies(
    project: UUID,
    user: CurrentUser,
    page: PageParams,
    stores: StoresDependency,
    jobs: JobsDependency,
) -> Page:
    return await services.list_studies(project, user, page, stores, jobs)


@router.post("", response_model=schemas.Study, status_code=status.HTTP_201_CREATED)
async def create_study(
    payload: schemas.StudyCreate,
    user: CurrentUser,
    stores: StoresDependency,
    minio: MinioDependency,
) -> schemas.Study:
    return await services.create_study(payload, user, stores, minio, tasks.enqueue)


@router.get("/{study_id}", response_model=schemas.Study)
async def get_study(
    study_id: UUID,
    user: CurrentUser,
    stores: StoresDependency,
    jobs: JobsDependency,
) -> schemas.Study:
    return await services.get_study(study_id, user, stores, jobs)


@router.post("/{study_id}/start", response_model=schemas.Study)
async def start_study(
    study_id: UUID,
    user: CurrentUser,
    stores: StoresDependency,
    minio: MinioDependency,
) -> schemas.Study:
    return await services.start_study(study_id, user, stores, minio, tasks.enqueue)


@router.post("/{study_id}/cancel", response_model=schemas.Study)
async def cancel_study(
    study_id: UUID,
    user: CurrentUser,
    stores: StoresDependency,
    jobs: JobsDependency,
) -> schemas.Study:
    return await services.cancel_study(study_id, user, stores, jobs)
