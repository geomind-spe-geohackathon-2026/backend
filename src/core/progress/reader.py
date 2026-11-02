import asyncio
from dataclasses import replace
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from src.core.clients.minio.blobs import BlobStore, BlobStoreDependency
from src.core.clients.postgres.repositories.base import DatabaseSession
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.progress import (
    ProgressRepository,
    ProjectFacts,
)
from src.core.gemini import case
from src.core.gemini.stored import stored_files


class ProgressReader:
    """The facts progress is computed from, with the values gemini finds missing."""

    def __init__(self, session: DatabaseSession, blobs: BlobStore) -> None:
        self.progress = ProgressRepository(session)
        self.cases = CaseVersionRepository(session)
        self.files = CaseFileRepository(session)
        self.blobs = blobs

    async def missing_count(self, project_id: UUID) -> int:
        """Count the values the latest case of a project lacks; zero without a case."""
        version = await self.cases.latest_version(project_id)
        if version is None:
            return 0
        files = await stored_files(
            await self.files.list_for_version(version.id), self.blobs
        )
        missing, _ = await asyncio.to_thread(case.validate, version.content, files)
        return len(missing)

    async def facts(self, project_ids: list[UUID]) -> dict[UUID, ProjectFacts]:
        """Return the facts of each project, empty ones included."""
        facts = await self.progress.facts(project_ids)
        return {
            project_id: replace(fact, case_missing=await self.missing_count(project_id))
            for project_id, fact in facts.items()
        }


def get_progress_reader(
    session: DatabaseSession,
    blobs: BlobStoreDependency,
) -> ProgressReader:
    return ProgressReader(session, blobs)


ProgressReaderDependency = Annotated[ProgressReader, Depends(get_progress_reader)]
