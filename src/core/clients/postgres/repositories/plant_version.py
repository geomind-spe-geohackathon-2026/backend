import hashlib
import json
from typing import Annotated, Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from fastapi import Depends
from src.core.clients.postgres.client import get_db, utc_now
from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.repositories.base import BaseRepository
from src.core.errors import ConflictError

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


def content_digest(content: dict[str, Any]) -> str:
    """Hash the canonical JSON: sorted keys, no spaces."""
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class PlantVersionRepository(BaseRepository):
    async def latest_version(self, project_id: UUID) -> PlantVersion | None:
        statement = (
            select(PlantVersion)
            .where(PlantVersion.project_id == project_id)
            .order_by(PlantVersion.number.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def version_by_number(
        self,
        project_id: UUID,
        number: int,
    ) -> PlantVersion | None:
        statement = select(PlantVersion).where(
            PlantVersion.project_id == project_id,
            PlantVersion.number == number,
        )
        return await self.session.scalar(statement)

    async def list_versions(self, project_id: UUID) -> list[PlantVersion]:
        """List versions, oldest first, without their content."""
        statement = (
            select(PlantVersion)
            .where(PlantVersion.project_id == project_id)
            .options(defer(PlantVersion.content, raiseload=True))
            .order_by(PlantVersion.number)
        )
        return list(await self.session.scalars(statement))

    async def all_versions(self, project_id: UUID) -> list[PlantVersion]:
        """List versions, oldest first, with their content."""
        statement = (
            select(PlantVersion)
            .where(PlantVersion.project_id == project_id)
            .order_by(PlantVersion.number)
        )
        return list(await self.session.scalars(statement))

    async def save_version(
        self,
        project_id: UUID,
        content: dict[str, Any],
        note: str,
        author_id: UUID,
    ) -> PlantVersion:
        """Save the next version; a save that loses the number retries once."""
        try:
            return await self._insert_next(project_id, content, note, author_id)
        except IntegrityError:
            await self.session.rollback()
        try:
            return await self._insert_next(project_id, content, note, author_id)
        except IntegrityError as error:
            await self.session.rollback()
            raise ConflictError("Plant version number is taken") from error

    async def _insert_next(
        self,
        project_id: UUID,
        content: dict[str, Any],
        note: str,
        author_id: UUID,
    ) -> PlantVersion:
        digest = content_digest(content)
        latest = await self.latest_version(project_id)
        if latest is not None and latest.digest == digest:
            raise ConflictError("Plant is the same as the latest version")

        version = PlantVersion(
            project_id=project_id,
            number=latest.number + 1 if latest else 1,
            plant_type=content["plant_type"],
            content=content,
            digest=digest,
            note=note,
            author_id=author_id,
        )
        self.session.add(version)
        await self.session.flush()
        await self.session.execute(
            update(Project).where(Project.id == project_id).values(updated=utc_now())
        )
        await self.session.commit()
        return version


def get_plant_version_repository(session: DatabaseSession) -> PlantVersionRepository:
    return PlantVersionRepository(session)
