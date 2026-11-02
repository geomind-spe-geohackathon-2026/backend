import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import defer

from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.repositories.base import BaseRepository
from src.core.errors import ConflictError


def content_digest(content: dict[str, Any]) -> str:
    """Hash the canonical JSON: sorted keys, no spaces."""
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class VersionRepository(BaseRepository):
    """Versions of one kind of document per project. Rows are never updated.

    A subclass names its ``model`` (a table with ``project_id``, ``number``,
    ``content``, ``digest``, ``note`` and ``author_id``) and the ``label`` used in
    error messages.
    """

    model: type[PlantVersion] | type[CaseVersion]
    label: str

    async def latest_version(self, project_id: UUID) -> Any | None:
        statement = (
            select(self.model)
            .where(self.model.project_id == project_id)
            .order_by(self.model.number.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def version_by_number(self, project_id: UUID, number: int) -> Any | None:
        statement = select(self.model).where(
            self.model.project_id == project_id,
            self.model.number == number,
        )
        return await self.session.scalar(statement)

    async def list_versions(self, project_id: UUID) -> list[Any]:
        """List versions, oldest first, without their content."""
        statement = (
            select(self.model)
            .where(self.model.project_id == project_id)
            .options(defer(self.model.content, raiseload=True))
            .order_by(self.model.number)
        )
        return list(await self.session.scalars(statement))

    async def all_versions(self, project_id: UUID) -> list[Any]:
        """List versions, oldest first, with their content."""
        statement = (
            select(self.model)
            .where(self.model.project_id == project_id)
            .order_by(self.model.number)
        )
        return list(await self.session.scalars(statement))

    async def save_version(
        self,
        project_id: UUID,
        content: dict[str, Any],
        note: str,
        author_id: UUID,
        digest: str | None = None,
    ) -> Any:
        """Save the next version; a save that loses the number retries once.

        ``digest`` stands for the content when the version also holds other data
        (a case with its files); it defaults to the hash of the content.
        """
        digest = digest or content_digest(content)
        try:
            return await self._insert_next(project_id, content, note, author_id, digest)
        except IntegrityError:
            await self.session.rollback()
        try:
            return await self._insert_next(project_id, content, note, author_id, digest)
        except IntegrityError as error:
            await self.session.rollback()
            raise ConflictError(f"{self.label} version number is taken") from error

    async def _insert_next(
        self,
        project_id: UUID,
        content: dict[str, Any],
        note: str,
        author_id: UUID,
        digest: str,
    ) -> Any:
        latest = await self.latest_version(project_id)
        if latest is not None and latest.digest == digest:
            raise ConflictError(
                f"{self.label} is the same as the latest version",
                details={"latest": latest.number},
            )

        version = self.model(
            project_id=project_id,
            number=latest.number + 1 if latest else 1,
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
