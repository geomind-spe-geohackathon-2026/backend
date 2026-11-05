from typing import Annotated
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, Query, status
from src.api.v1.design.study import schemas, services, tasks
from src.core.clients.minio.blobs import BlobStoreDependency
from src.core.clients.postgres.client import get_db
from src.core.clients.redis.repositories.job import JobRepository, get_job_repository
from src.core.pagination.page import Page, PageParams
from src.core.security.access import CurrentUser

router = APIRouter(prefix="/study", tags=["Study"])


def get_stores(session: Annotated[AsyncSession, Depends(get_db)]) -> services.Stores:
    return services.Stores.open(session)


StoresDependency = Annotated[services.Stores, Depends(get_stores)]
JobsDependency = Annotated[JobRepository, Depends(get_job_repository)]


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
    blobs: BlobStoreDependency,
) -> schemas.Study:
    return await services.create_study(payload, user, stores, blobs, tasks.enqueue)


@router.get("/{study_id}/structures", response_model=schemas.StudyStructures)
async def read_structures(
    study_id: UUID,
    user: CurrentUser,
    stores: StoresDependency,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> schemas.StudyStructures:
    """The best unique structures of an evolve study, ranked; 404 structures_not_found."""
    return await services.read_structures(study_id, user, stores, limit)


@router.get("/{study_id}/structures/{rank}/plant", response_model=schemas.StructurePlant)
async def read_structure_plant(
    study_id: UUID, rank: int, user: CurrentUser, stores: StoresDependency
) -> schemas.StructurePlant:
    """The plant of the structure at ``rank``; 404 structure_plant_not_stored when gemini kept none."""
    return await services.structure_plant(study_id, rank, user, stores)


@router.post(
    "/{study_id}/structures/{rank}/plant",
    response_model=schemas.SavedStructurePlant,
    status_code=status.HTTP_201_CREATED,
)
async def save_structure_plant(
    study_id: UUID, rank: int, user: CurrentUser, stores: StoresDependency
) -> schemas.SavedStructurePlant:
    """Save the plant of the structure at ``rank`` as the project's next plant version."""
    return await services.save_structure_plant(study_id, rank, user, stores)


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
    blobs: BlobStoreDependency,
) -> schemas.Study:
    return await services.start_study(study_id, user, stores, blobs, tasks.enqueue)


@router.post("/{study_id}/cancel", response_model=schemas.Study)
async def cancel_study(
    study_id: UUID,
    user: CurrentUser,
    stores: StoresDependency,
    jobs: JobsDependency,
) -> schemas.Study:
    return await services.cancel_study(study_id, user, stores, jobs)
