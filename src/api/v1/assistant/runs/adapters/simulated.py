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
            if found is None:
                return
            reference = found["output"]["reference"]
            results = ResultRepository(session)
            known = await results.all_for_project(self.project_id)
            if any(item.content.get("simulation") == reference for item in known):
                return
            parts = await self.parts(session, reference.removeprefix(RESULT_PREFIX))
            if parts is None:
                logger.warning("assistant simulation not recorded: run files missing")
                return
            plant_data, case_data, files, data = parts
            outcome = await asyncio.to_thread(
                study.stored_run, plant_data, case_data, files, data
            )
            if outcome is None:
                logger.warning("assistant simulation not recorded: gemini refused it")
                return
            report = outcome["report"]
            normalised = await asyncio.to_thread(plant.validate_content, plant_data)
            plant_version = await self.plant_version(
                session, content_digest(normalised)
            )
            case_version = await self.case_version(
                session, files_digest(case_data, files)
            )
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
            await ActivityRepository(session).add(
                self.project_id,
                "agent",
                "assistant",
                f"Result {name} recorded",
                RESULTS_ROUTE,
                str(result.id),
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
