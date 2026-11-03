from typing import Any

import geomind as gd

from src.core.errors import NotImplementedYetError, ValidationFailedError

KNOWLEDGE = "knowledge"
EXPERIENCE = "experience"
SECTIONS = (KNOWLEDGE, EXPERIENCE)


def is_available() -> bool:
    """Tell whether this geomind has its public memory module."""
    return getattr(gd, "memory", None) is not None


def public_memory() -> Any:
    """Return geomind's public memory module, or refuse while geomind has none."""
    memory = getattr(gd, "memory", None)
    if memory is None:
        raise NotImplementedYetError("geomind memory (gd.memory)")
    return memory


def problem_of(error: Exception) -> dict[str, str]:
    path = getattr(error, "path", None) or "entry"
    return {path: str(error)}


def checked_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a knowledge entry geomind accepts, or raise ``validation_failed``.

    geomind's check is the one its ``write_memory`` tool runs, so a person and an agent
    are held to the same rule: a value with its source.
    """
    memory = public_memory()
    try:
        return dict(memory.check_knowledge(entry))
    except gd.errors.GeomindError as error:
        raise ValidationFailedError(problem_of(error)) from error


def catalogue_entries(rows: list[dict[str, Any]], origin: str) -> list[dict[str, Any]]:
    """Return the knowledge entries of catalogue rows, as ``geomind memory seed``."""
    memory = public_memory()
    try:
        return [dict(entry) for entry in memory.catalogue_entries(rows, origin)]
    except gd.errors.GeomindError as error:
        raise ValidationFailedError(problem_of(error)) from error


def similarity_threshold() -> float | None:
    """Return the similarity an experience entry needs to be shown to an agent."""
    memory = getattr(gd, "memory", None)
    value = getattr(memory, "SIMILARITY", None) if memory is not None else None
    return float(value) if isinstance(value, (int, float)) else None
