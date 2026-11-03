from typing import Any

import geomind as gd

from src.core.logging.logger import get_logger

logger = get_logger(__name__)


def suggestions_for(
    problem: dict[str, Any], files: list[str], project: dict[str, Any] | None
) -> list[dict[str, str]]:
    """Return geomind's next steps for a chat that has no messages yet.

    No model is called. A geomind without ``gd.suggest``, or one that fails, gives
    none: a missing suggestion never breaks a page.
    """
    suggest = getattr(gd, "suggest", None)
    if suggest is None:
        return []
    try:
        found = suggest(problem, files, project=project)
    except Exception:
        logger.exception("geomind could not suggest next steps")
        return []
    return [
        {"label": str(item["label"]), "message": str(item["message"])}
        for item in found or []
        if item.get("label") and item.get("message")
    ]
