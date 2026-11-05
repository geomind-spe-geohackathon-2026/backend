from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.clients.postgres.models.study import Study
from src.core.clients.postgres.repositories.progress import ProgressRepository
from src.core.progress.reader import has_economics
from src.core.progress.states import build_progress, economics_step


async def newest_study_case(session: AsyncSession, project_id: UUID) -> int | None:
    statement = (
        select(Study.case_version)
        .where(Study.project_id == project_id, Study.case_version.is_not(None))
        .order_by(Study.created.desc())
        .limit(1)
    )
    return await session.scalar(statement)


async def economics_state(session: AsyncSession, project_id: UUID) -> dict[str, str]:
    """Return the progress item of the latest case version's economics (QA-194).

    ``{state: done, label: Set}`` when the case has a non-empty ``economics`` section, else
    ``{state: empty, label: Not set}``; geomind's next-step chips then offer "Set the
    economics" before a plant.
    """
    has = (await has_economics(session, [project_id]))[project_id]
    return economics_step(has).model_dump()


async def project_state(session: AsyncSession, project_id: UUID) -> dict[str, Any]:
    """Return where a project stands, as geomind's next-step suggestions read it.

    The five steps of the project's progress, the latest case and plant versions, the
    case version of the newest study, whether the case changed after that study, and the
    state of the latest case's economics.
    """
    facts = (await ProgressRepository(session).facts([project_id]))[project_id]
    steps = build_progress(facts).model_dump()
    study_case = await newest_study_case(session, project_id)
    changed = (
        facts.case_version is not None
        and study_case is not None
        and facts.case_version > study_case
    )
    return {
        **steps,
        "case_version": facts.case_version,
        "plant_version": facts.plant_version,
        "study_case_version": study_case,
        "case_changed_after_study": changed,
        "economics": await economics_state(session, project_id),
    }
