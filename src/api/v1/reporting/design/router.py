from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, Response
from src.api.v1.reporting.design import schemas, services
from src.core.clients.minio.blobs import BlobStoreDependency
from src.core.clients.postgres.client import get_db
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.security.access import CurrentUser

router = APIRouter(prefix="/design", tags=["Design reports"])


def get_repositories(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> services.Repositories:
    return services.Repositories(
        ProjectRepository(session),
        ResultRepository(session),
        StudyRepository(session),
        RunRepository(session),
        ActivityRepository(session),
        CaseVersionRepository(session),
        CaseFileRepository(session),
    )


RepositoriesDependency = Annotated[services.Repositories, Depends(get_repositories)]


@router.get("/parts", response_model=list[schemas.ReportPart])
async def list_parts(_user: CurrentUser) -> list[schemas.ReportPart]:
    return services.list_parts()


@router.post("/preview", response_model=schemas.Report)
async def preview_report(
    payload: schemas.ReportRequest,
    user: CurrentUser,
    repositories: RepositoriesDependency,
    blobs: BlobStoreDependency,
) -> schemas.Report:
    return await services.preview_report(payload, user, repositories, blobs)


@router.post(
    "/export",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}, "application/pdf": {}}}},
)
async def export_report(
    payload: schemas.ReportExport,
    user: CurrentUser,
    repositories: RepositoriesDependency,
    blobs: BlobStoreDependency,
) -> Response:
    export = await services.export_report(payload, user, repositories, blobs)
    return Response(
        content=export.content,
        media_type=export.media_type,
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )
