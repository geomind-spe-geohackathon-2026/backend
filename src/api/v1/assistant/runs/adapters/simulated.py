"""The last plain ``simulate`` of an assistant run becomes a result (QA-135, option C).

A chat ``simulate`` saves the design it ran as the project plant (QA-092) but wrote no
result, so Study and Results read "Out of date" right after a fresh full-year run. When the
root run finishes, its last successful ``simulate`` is added to the project's results: no
study, named ``simulation <design>``, with the case and plant versions it ran on when they
match a saved version (else ``None``, as for an agent study). Only the last one, so a chat
that simulates many times adds one row (user, 2026-11-05).
"""

import asyncio
import logging
from typing import Any
from uuid import UUID

import geomind as gd
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.case_versions import files_digest
from src.core.clients.postgres.models.run_event import RunEvent
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.result import ResultRepository
from src.core.clients.postgres.repositories.run_artifact import (
    RunArtifactRepository,
)
from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.postgres.repositories.study import StudyRepository
from src.core.clients.postgres.repositories.version import content_digest
from src.core.errors import AppError
from src.core.gemini import evaluate, plant, study
from src.core.routes import RESULTS_ROUTE

RUN_FINISHED = "run.finished"
TOOL_RECORDED = "tool.result"
SIMULATE_TOOL = "simulate"
FROM_TOOL = "tool"
RESULT_PREFIX = "result/"
DESIGN_PREFIX = "design/"
FILE_SUFFIX = ".file"
RUN_PARTS = ("plant", "case", "files", "results")
NAME = "simulation {name}"
PROJECT_PLANT = "project plant"
STUDY_PREFIX = "study/"
STUDY_KINDS = ("sensitivity", "sample")
"""The study methods whose result is a tornado or a spread, not a simulated run (QA-274)."""

logger = logging.getLogger(__name__)


WHAT_IF_INPUTS = ("changes", "start", "end")
"""``simulate`` inputs that make a what-if: a changed or shortened run of a design, no result."""


def is_what_if(data: dict[str, Any]) -> bool:
    """Tell a ``simulate`` with changes or its own period, which never becomes a result (QA-223)."""
    given = data.get("input")
    if not isinstance(given, dict):
        return False
    return any(given.get(name) for name in WHAT_IF_INPUTS)


def last_simulation(rows: list[RunEvent]) -> dict[str, Any] | None:
    """Return the newest successful plain ``simulate`` tool result of ``rows`` (newest first).

    A what-if (``changes``, ``start`` or ``end`` given) is skipped: it saves no design, and the
    result row must hold the chosen design, not a trial (QA-223).
    """
    for row in rows:
        data = row.data
        output = data.get("output")
        if (
            data.get("tool") == SIMULATE_TOOL
            and not is_what_if(data)
            and not data.get("is_error")
            and data.get("source") == FROM_TOOL
            and isinstance(output, dict)
            and str(output.get("reference", "")).startswith(RESULT_PREFIX)
        ):
            return data
    return None


def name_of(given: dict[str, Any], plant_data: dict[str, Any]) -> str:
    design = given.get("design")
    if isinstance(design, str) and design.startswith(DESIGN_PREFIX):
        return NAME.format(name=design.removeprefix(DESIGN_PREFIX))
    found = plant_data.get("name")
    return NAME.format(
        name=found if isinstance(found, str) and found else PROJECT_PLANT
    )


async def design_digest(design: Any) -> str | None:
    """Return the digest of a design as a saved plant version has it; ``None`` if unreadable."""
    if not isinstance(design, dict):
        return None
    try:
        normalised = await asyncio.to_thread(plant.validate_content, design)
    except AppError:
        return None
    return content_digest(normalised)


async def recorded_design(
    known: list[Any], digest: str | None, case_version: int | None
) -> bool:
    """Tell whether a design result of the same design on the same case version exists (QA-215).

    Only design results count: a sensitivity or uncertainty result of the design is another
    view of it. Without a digest or a saved case version nothing is known to be the same.
    """
    if digest is None or case_version is None:
        return False
    for item in known:
        if item.case_version != case_version:
            continue
        if evaluate.role_of(item.content.get("run") or {}) != evaluate.DESIGN_ROLE:
            continue
        if await design_digest(item.content.get("design")) == digest:
            return True
    return False


class SimulationRecorder(gd.callbacks.Callback):
    """Add the last plain ``simulate`` of a finished assistant run to the results."""

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        run_id: UUID,
        chat_id: UUID,
        project_id: UUID,
    ) -> None:
        self.factory = factory
        self.run_id = run_id
        self.chat_id = chat_id
        self.project_id = project_id

    async def on_event(self, engine: Any, event: Any) -> None:
        """Record the run's last simulation when the root run finishes."""
        if event.type != RUN_FINISHED or event.parent is not None:
            return
        try:
            await self.record()
        except AppError as error:
            logger.warning("assistant simulation not recorded: %s", error.code)

    async def record(self) -> None:
        async with self.factory() as session:
            rows = await RunEventRepository(session).of_type(self.run_id, TOOL_RECORDED)
            found = last_simulation(rows)
            ran = None
            if found is not None:
                ran = await self.ran(session, found["output"]["reference"])
            if ran is not None:
                await self.add_simulation(session, found, ran)
            await self.add_studies(session, found, ran)
            await self.fill_plant_versions(session)

    async def ran(
        self, session: AsyncSession, reference: str
    ) -> tuple[tuple[Any, ...], dict[str, Any]] | None:
        """Return the stored parts of a chat ``simulate`` and gemini's outcome of them."""
        parts = await self.parts(session, reference.removeprefix(RESULT_PREFIX))
        if parts is None:
            logger.warning("assistant simulation not recorded: run files missing")
            return None
        plant_data, case_data, files, data = parts
        outcome = await asyncio.to_thread(
            study.stored_run, plant_data, case_data, files, data
        )
        if outcome is None:
            logger.warning("assistant simulation not recorded: gemini refused it")
            return None
        return parts, outcome

    async def add_simulation(
        self,
        session: AsyncSession,
        found: dict[str, Any],
        ran: tuple[tuple[Any, ...], dict[str, Any]],
    ) -> None:
        reference = found["output"]["reference"]
        results = ResultRepository(session)
        known = await results.all_for_project(self.project_id)
        if any(item.content.get("simulation") == reference for item in known):
            return
        (plant_data, case_data, files, _), outcome = ran
        report = outcome["report"]
        digest = await design_digest(plant_data)
        plant_version = (
            None if digest is None else await self.plant_version(session, digest)
        )
        case_version = await self.case_version(session, files_digest(case_data, files))
        if await recorded_design(known, digest, case_version):
            logger.info(
                "assistant simulation not recorded: same design already a result"
            )
            return
        summary = evaluate.summarise(report)
        name = name_of(found.get("input") or {}, plant_data)
        result = await results.create(
            {
                "project_id": self.project_id,
                "study_id": None,
                "name": name,
                "case_version": case_version,
                "plant_version": plant_version,
                "summary": summary["summary"],
                "content": {
                    "capacities": summary["capacities"],
                    "constraints": summary["constraints"],
                    "series": [],
                    "report": report,
                    "run": {},
                    "design": outcome["design"],
                    "coverage": outcome["coverage"],
                    "simulation": reference,
                },
            }
        )
        await self.tell(session, f"Result {name} recorded", result.id)

    async def add_studies(
        self,
        session: AsyncSession,
        found: dict[str, Any] | None,
        ran: tuple[tuple[Any, ...], dict[str, Any]] | None,
    ) -> None:
        """Add a result per sensitivity or uncertainty study of the run (QA-274).

        geomind's ``sensitivity`` and ``sample_uncertainty`` store their tornado or draws in
        ``study/<name>`` but no simulated run, so the study row had no result and the Report
        never offered it. The result keeps the study's figures as ``run.found`` (what
        ``tornado_of`` and ``spread_of`` read) beside the report of the study's design on the
        case of the run's last plain ``simulate``: that run itself when it is the same design,
        else a new simulation of the design. A run without a plain ``simulate`` gives no case,
        so its studies stay without a result.
        """
        studies = [
            item
            for item in await StudyRepository(session).all_for_project(self.project_id)
            if item.started_by_run_id == self.run_id and item.kind in STUDY_KINDS
        ]
        if not studies:
            return
        results = ResultRepository(session)
        known = {
            item.study_id for item in await results.all_for_project(self.project_id)
        }
        artifacts = RunArtifactRepository(session)
        for item in studies:
            if item.id in known:
                continue
            stored = await artifacts.newest_for_chat(
                self.chat_id, f"{STUDY_PREFIX}{item.name}"
            )
            data = stored.data if stored is not None else None
            if not isinstance(data, dict) or not isinstance(data.get("result"), dict):
                logger.warning("assistant study %s has no stored result", item.name)
                continue
            outcome = await self.study_outcome(session, data, found, ran)
            if outcome is None:
                logger.warning(
                    "assistant study %s not recorded: no design run", item.name
                )
                continue
            report = outcome["report"]
            summary = evaluate.summarise(report)
            digest = await design_digest(outcome["design"])
            result = await results.create(
                {
                    "project_id": self.project_id,
                    "study_id": item.id,
                    "name": item.name,
                    "case_version": item.case_version,
                    "plant_version": None
                    if digest is None
                    else await self.plant_version(session, digest),
                    "summary": summary["summary"],
                    "content": {
                        "capacities": summary["capacities"],
                        "constraints": summary["constraints"],
                        "series": [],
                        "report": report,
                        "run": {"found": data["result"]},
                        "design": outcome["design"],
                        "coverage": outcome["coverage"],
                    },
                }
            )
            await self.tell(session, f"Result {item.name} recorded", result.id)

    async def study_outcome(
        self,
        session: AsyncSession,
        data: dict[str, Any],
        found: dict[str, Any] | None,
        ran: tuple[tuple[Any, ...], dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        """Return the report, coverage and design of the design a study varied."""
        if found is None or ran is None:
            return None
        read = (data.get("designs") or {}).get("read") or []
        reference = read[0] if read else None
        if reference is None or reference == (found.get("input") or {}).get("design"):
            return ran[1]
        design = await RunArtifactRepository(session).newest_for_chat(
            self.chat_id, reference
        )
        if design is None or not isinstance(design.data, dict):
            return None
        (_, case_data, files, _), _ = ran
        return await asyncio.to_thread(
            evaluate.design_outcome, design.data, case_data, files
        )

    async def fill_plant_versions(self, session: AsyncSession) -> None:
        """Give each result of this run's studies the saved plant version of its design (QA-215).

        An agent study's result is written without a plant version; the version is found by the
        design's digest among the saved ones, never made (QA-237). A design no version holds,
        such as an optimiser's new best, keeps none.
        """
        studies = {
            item.id
            for item in await StudyRepository(session).all_for_project(self.project_id)
            if item.started_by_run_id == self.run_id
        }
        changed = False
        for item in await ResultRepository(session).all_for_project(self.project_id):
            if item.study_id not in studies or item.plant_version is not None:
                continue
            digest = await design_digest(item.content.get("design"))
            number = (
                None if digest is None else await self.plant_version(session, digest)
            )
            if number is not None:
                item.plant_version = number
                changed = True
        if changed:
            await session.commit()

    async def tell(self, session: AsyncSession, text: str, result_id: UUID) -> None:
        await ActivityRepository(session).add(
            self.project_id, "agent", "assistant", text, RESULTS_ROUTE, str(result_id)
        )

    async def parts(
        self, session: AsyncSession, identifier: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes], bytes] | None:
        """Return the plant, case, case files and results geomind kept for a run."""
        artifacts = RunArtifactRepository(session)
        found = []
        for part in RUN_PARTS:
            row = await artifacts.newest_for_chat(self.chat_id, f"{identifier}.{part}")
            if row is None:
                return None
            found.append(row.data)
        plant_data, case_data, digests, data = found
        if not isinstance(data, bytes) or not isinstance(digests, dict):
            return None
        files = {}
        for name, digest in digests.items():
            row = await artifacts.newest_for_chat(
                self.chat_id, f"{digest}{FILE_SUFFIX}"
            )
            if row is None or not isinstance(row.data, bytes):
                return None
            files[name] = row.data
        return plant_data, case_data, files, data

    async def plant_version(self, session: AsyncSession, digest: str) -> int | None:
        rows = await PlantVersionRepository(session).list_versions(self.project_id)
        found = [row.number for row in rows if row.digest == digest]
        return found[-1] if found else None

    async def case_version(self, session: AsyncSession, digest: str) -> int | None:
        rows = await CaseVersionRepository(session).list_versions(self.project_id)
        found = [row.number for row in rows if row.digest == digest]
        return found[-1] if found else None
