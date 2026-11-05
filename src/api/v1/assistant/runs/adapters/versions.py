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
PLANT_TOOLS = {
    "build_plant": "built",
    "patch_plant": "changed",
    "merge_designs": "changed",
    "set_ranges": "changed",
    "size_plant": "sized",
    "optimize": "optimised",
}
SIMULATE_TOOL = "simulate"
SIMULATED = "simulated"
FROM_TOOL = "tool"
ACTOR_KIND = "agent"
ACTOR_NAME = "assistant"
CASE_NOTE = "Case set by the assistant"
PLANT_NOTE = "Plant {name} {how} by the assistant"

NOTE_PATHS = 6
FILES_PATH = "files"

logger = logging.getLogger(__name__)


def keyed(items: list[Any]) -> dict[str, Any] | None:
    """Return a list of named dicts by name, or ``None`` when it is not one."""
    named = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            return None
        named[item["name"]] = item
    return named if len(named) == len(items) else None


def changed_paths(old: Any, new: Any, path: str = "") -> list[tuple[str, str]]:
    """Return ``(path, how)`` of what differs, ``how`` one of added, removed, changed.

    Dicts are compared key by key and lists of named items (``requirements``) by name,
    so a note can say which rule or value changed.
    """
    if old == new:
        return []
    if isinstance(old, list) and isinstance(new, list):
        old_named, new_named = keyed(old), keyed(new)
        if old_named is not None and new_named is not None:
            old, new = old_named, new_named
    if not isinstance(old, dict) or not isinstance(new, dict):
        return [(path, "changed")]
    found = []
    for key in list(old) + [key for key in new if key not in old]:
        inner = f"{path}.{key}" if path else str(key)
        if key not in new:
            found.append((inner, "removed"))
        elif key not in old:
            found.append((inner, "added"))
        else:
            found.extend(changed_paths(old[key], new[key], inner))
    return found


def case_note(
    old: dict[str, Any] | None,
    new: dict[str, Any],
    old_files: set[str],
    new_files: set[str],
) -> str:
    """Write the note of a case the assistant saved, naming what changed (QA-110).

    The note was always "Case set by the assistant", so History could not tell versions
    apart; now it names up to ``NOTE_PATHS`` changed paths and files, and how many more.
    """
    if old is None:
        return CASE_NOTE
    changes = changed_paths(old, new)
    changes += [
        (f"{FILES_PATH}.{name}", "added") for name in sorted(new_files - old_files)
    ]
    changes += [
        (f"{FILES_PATH}.{name}", "removed") for name in sorted(old_files - new_files)
    ]
    if not changes:
        return f"{CASE_NOTE}: files changed"
    shown = "; ".join(f"{path} {how}" for path, how in changes[:NOTE_PATHS])
    more = len(changes) - NOTE_PATHS
    return f"{CASE_NOTE}: {shown}" + (f"; {more} more" if more > 0 else "")


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


def stored_design(event: Any) -> tuple[str, str] | None:
    """Return the ``design/<name>`` a tool stored or simulated, and how, or ``None``.

    A tool that stores one design under its ``name`` input (build, patch, merge,
    ranges, sizing, optimisation), or ``simulate`` on a stored ``design``, makes that
    design the project plant: the plant the agents work on is the one the Plant,
    Study and Results pages show (QA-092: only ``build_plant`` was saved, so a
    patched, simulated design never reached the Plant page). ``union_designs``
    stores a superstructure for evolve, not a plant, and saves nothing.
    """
    if event.type != TOOL_RECORDED or event.is_error or event.source != FROM_TOOL:
        return None
    given = event.input or {}
    if event.tool == SIMULATE_TOOL:
        design = given.get("design")
        if isinstance(design, str) and design.startswith(DESIGN_ARTIFACT):
            return design, SIMULATED
        return None
    how = PLANT_TOOLS.get(event.tool)
    name = given.get("name")
    if how is None or not isinstance(name, str) or not name:
        return None
    return f"{DESIGN_ARTIFACT}{name}", how


class VersionRecorder(gd.callbacks.Callback):
    """Save the case and the plant a run settles as the project's next versions.

    A case gemini accepted (``state.changed`` on ``/case``) becomes a case version with
    the files it names; a design a plant tool stored or ``simulate`` ran becomes a
    plant version. Content equal to the latest version saves nothing. It writes with
    its own async sessions on the event loop, as ``StudyRecorder`` does, and runs
    gemini off the loop.
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
        stored = stored_design(event)
        if stored is not None:
            await self.guarded(self.save_plant(*stored))

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
            rows = CaseFileRepository(session)
            before = [] if latest is None else await rows.list_for_version(latest.id)
            note = case_note(
                None if latest is None else latest.content,
                content,
                {row.name for row in before},
                set(files),
            )
            for data in files.values():
                await self.blobs.put(object_key(self.project_id, data), data)
            version = await versions.save_version(
                self.project_id,
                content,
                note,
                self.author_id,
                digest,
                {"missing": len(missing)},
            )
            for name, data in files.items():
                key = object_key(self.project_id, data)
                await rows.add(self.project_id, version.id, name, len(data), key)
            await ActivityRepository(session).add(
                self.project_id,
                ACTOR_KIND,
                ACTOR_NAME,
                f"Saved case version {version.number}",
                CASE_ROUTE,
                str(version.number),
            )

    async def save_plant(self, design: str, how: str) -> None:
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
                self.project_id,
                content,
                PLANT_NOTE.format(name=name, how=how),
                self.author_id,
            )
            await ActivityRepository(session).add(
                self.project_id,
                ACTOR_KIND,
                ACTOR_NAME,
                f"Saved plant version {version.number}",
                PLANT_ROUTE,
                str(version.number),
            )
