import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from celery import shared_task
from src.api.v1.identity.me import services
from src.core.clients.postgres.client import create_postgres_client
from src.core.clients.postgres.repositories.user import UserRepository

DELETE_ACCOUNT_TASK = "identity.me.delete_account"


async def _delete_account(user_id: UUID) -> None:
    engine = create_postgres_client()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await services.delete_account(user_id, UserRepository(session))
    finally:
        await engine.dispose()


@shared_task(name=DELETE_ACCOUNT_TASK, ignore_result=True)
def delete_account(user_id: str) -> None:
    asyncio.run(_delete_account(UUID(user_id)))


JOB_MODULES = (__name__,)
