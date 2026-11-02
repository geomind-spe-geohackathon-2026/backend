from src.core.clients.postgres.models.case_version import CaseVersion
from src.core.clients.postgres.repositories.base import DatabaseSession
from src.core.clients.postgres.repositories.version import VersionRepository


class CaseVersionRepository(VersionRepository):
    model = CaseVersion
    label = "Case"


def get_case_version_repository(session: DatabaseSession) -> CaseVersionRepository:
    return CaseVersionRepository(session)
