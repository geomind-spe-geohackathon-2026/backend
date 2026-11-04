"""Save the case and the plant a run settles as new versions of the project."""

import asyncio
import logging
from typing import Any
from uuid import UUID

import geomind as gd
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.case_versions import files_digest, named_files, object_key
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import (
    CaseVersionRepository,
)
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.run_artifact import (
    RunArtifactRepository,
)
from src.core.clients.postgres.repositories.version import content_digest
from src.core.errors import AppError, ConflictError
from src.core.gemini import case, plant
from src.core.routes import CASE_ROUTE, PLANT_ROUTE

STATE_CHANGED = "state.changed"
TOOL_RECORDED = "tool.result"
CASE_PATH = "/case"
SETTING_OPS = ("add", "replace")
CASE_ARTIFACT = "case/"
DESIGN_ARTIFACT = "design/"
PLANT_TOOLS = ("build_plant",)
FROM_TOOL = "tool"
ACTOR_KIND = "agent"
ACTOR_NAME = "assistant"
CASE_NOTE = "Case set by the assistant"
PLANT_NOTE = "Plant {name} built by the assistant"

logger = logging.getLogger(__name__)


def accepted_case(event: Any) -> dict[str, Any] | None:
    """Return the case a ``state.changed`` event sets, or ``None``.

    geomind changes ``/case`` only once gemini accepted the case, after its files
    are stored as the chat artifacts ``case/<name>``.
    """
    if event.type != STATE_CHANGED:
        return None
    found = None
    for change in event.changes:
        if (
            change.get("path") == CASE_PATH
            and change.get("op") in SETTING_OPS
            and isinstance(change.get("value"), dict)
        ):
            found = change["value"]
    return found


def stored_design(event: Any) -> str | None:
    """Return the ``design/<name>`` a successful ``build_plant`` stored, or ``None``."""
    if event.type != TOOL_RECORDED or event.tool not in PLANT_TOOLS:
        return None
    if event.is_error or event.source != FROM_TOOL:
        return None
    name = (event.input or {}).get("name")
    return f"{DESIGN_ARTIFACT}{name}" if isinstance(name, str) and name else None


class VersionRecorder(gd.callbacks.Callback):
    """Save the case and the plant a run settles as the project's next versions.

    A case gemini accepted (``state.changed`` on ``/case``) becomes a case version with
    the files it names; a plant ``build_plant`` stored becomes a plant version. Content
    equal to the latest version saves nothing. It writes with its own async sessions
    on the event loop, as ``StudyRecorder`` does, and runs gemini off the loop.
    """

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        blobs: BlobStore,
        chat_id: UUID,
        project_id: UUID,
        author_id: UUID,
    ) -> None:
        self.factory = factory
        self.blobs = blobs
        self.chat_id = chat_id
        self.project_id = project_id
        self.author_id = author_id

    async def on_event(self, engine: Any, event: Any) -> None:
        """Save a version when the event settles a case or a plant."""
        content = accepted_case(event)
        if content is not None:
            await self.guarded(self.save_case(content))
            return
        design = stored_design(event)
        if design is not None:
            await self.guarded(self.save_plant(design))

    async def guarded(self, saving: Any) -> None:
        try:
            await saving
        except ConflictError:
            return
        except AppError as error:
            logger.warning("assistant version not saved: %s", error.code)

    async def save_case(self, content: dict[str, Any]) -> None:
        async with self.factory() as session:
            artifacts = RunArtifactRepository(session)

            async def read(name: str) -> bytes | None:
                row = await artifacts.newest_for_chat(
                    self.chat_id, f"{CASE_ARTIFACT}{name}"
                )
                data = None if row is None else row.data
                return data if isinstance(data, bytes) else None

            files = await named_files(content, read)
            versions = CaseVersionRepository(session)
            digest = files_digest(content, files)
            latest = await versions.latest_version(self.project_id)
            if latest is not None and latest.digest == digest:
                return
            missing, problems = await asyncio.to_thread(case.validate, content, files)
            if problems:
                logger.warning("assistant case not saved: gemini found problems")
                return
            for data in files.values():
                await self.blobs.put(object_key(self.project_id, data), data)
            version = await versions.save_version(
                self.project_id,
                content,
                CASE_NOTE,
                self.author_id,
                digest,
                {"missing": len(missing)},
            )
            rows = CaseFileRepository(session)
            for name, data in files.items():
                key = object_key(self.project_id, data)
                await rows.add(self.project_id, version.id, name, len(data), key)
            await ActivityRepository(session).add(
                self.project_id,
                ACTOR_KIND,
                ACTOR_NAME,
                f"Saved case version {version.number}",
                CASE_ROUTE,
            )

    async def save_plant(self, design: str) -> None:
        async with self.factory() as session:
            row = await RunArtifactRepository(session).newest_for_chat(
                self.chat_id, design
            )
            if row is None or not isinstance(row.data, dict):
                return
            content = await asyncio.to_thread(plant.validate_content, row.data)
            versions = PlantVersionRepository(session)
            latest = await versions.latest_version(self.project_id)
            if latest is not None and latest.digest == content_digest(content):
                return
            name = design.removeprefix(DESIGN_ARTIFACT)
            version = await versions.save_version(
                self.project_id, content, PLANT_NOTE.format(name=name), self.author_id
            )
            await ActivityRepository(session).add(
                self.project_id,
                ACTOR_KIND,
                ACTOR_NAME,
                f"Saved plant version {version.number}",
                PLANT_ROUTE,
            )
