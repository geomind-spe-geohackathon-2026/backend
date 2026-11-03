import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from celery import shared_task
from src.api.v1.workspace.rag import services
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.minio.client import create_minio_client
from src.core.clients.postgres.client import create_postgres_client
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.settings import settings

TASK_MODULES = (__name__,)


async def extract(document_id: UUID) -> None:
    engine = create_postgres_client()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        async with factory() as session:
            await services.extract_document(
                document_id,
                RagDocumentRepository(session),
                BlobStore(create_minio_client(), settings.MINIO_BUCKET_NAME),
            )
    finally:
        await engine.dispose()


@shared_task(bind=True, name=services.EXTRACT_TASK)
def extract_document(self, document_id: str) -> None:
    """Extract the text of an uploaded document so the assistant can search it."""
    asyncio.run(extract(UUID(document_id)))
