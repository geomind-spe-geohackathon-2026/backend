from fastapi import APIRouter, Request, status
from starlette.concurrency import run_in_threadpool

from src.api.v1.identity.me import jobs, schemas

router = APIRouter(prefix="/me", tags=["Me"])


@router.delete(
    "",
    response_model=schemas.AccountDeletionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_me(request: Request) -> schemas.AccountDeletionResponse:
    from src.celery import app as celery_app

    await run_in_threadpool(
        celery_app.send_task,
        jobs.DELETE_ACCOUNT_TASK,
        args=[str(request.state.user_id)],
    )
    return schemas.AccountDeletionResponse(
        message="Account deletion has been scheduled"
    )
