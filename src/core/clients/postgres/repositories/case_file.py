from uuid import UUID

from sqlalchemy import select

from src.core.clients.postgres.models.case_file import CaseFile
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession


class CaseFileRepository(BaseRepository):
    async def add(
        self,
        project_id: UUID,
        case_version_id: UUID,
        name: str,
        size: int,
        object_key: str,
    ) -> CaseFile:
        file = CaseFile(
            project_id=project_id,
            case_version_id=case_version_id,
            name=name,
            size=size,
            object_key=object_key,
        )
        self.session.add(file)
        await self.session.commit()
        return file

    async def list_for_version(self, case_version_id: UUID) -> list[CaseFile]:
        statement = (
            select(CaseFile)
            .where(CaseFile.case_version_id == case_version_id)
            .order_by(CaseFile.name)
        )
        return list(await self.session.scalars(statement))

    async def object_keys(self, project_id: UUID) -> list[str]:
        """Return each stored object of the project once; versions share objects."""
        statement = select(CaseFile.object_key).where(CaseFile.project_id == project_id)
        return sorted(set(await self.session.scalars(statement)))

    async def get(self, case_version_id: UUID, name: str) -> CaseFile | None:
        statement = select(CaseFile).where(
            CaseFile.case_version_id == case_version_id,
            CaseFile.name == name,
        )
        return await self.session.scalar(statement)


def get_case_file_repository(session: DatabaseSession) -> CaseFileRepository:
    return CaseFileRepository(session)
