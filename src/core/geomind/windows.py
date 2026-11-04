"""The context window of a model, as geomind itself looks it up.

geomind reads the provider's model list once per process (``load_windows``) and then
answers ``context_window(model)`` from it, or from ``GEOMIND_CONTEXT_WINDOW`` when that
is set. A worker process has the list loaded by the run itself; the API process loads
it here, once, before it shows windows. A model geomind knows no window for takes the
backend's single setting from ``src.core.assistant.context``.
"""

from collections.abc import Iterable

import geomind as gd
from geomind import context, providers

from src.core.assistant.context import context_window as configured_window
from src.core.logging.logger import get_logger

logger = get_logger(__name__)

fetch_windows = providers.openrouter.fetch_context_windows
_state = {"tried": False}


def forget() -> None:
    """Drop the loaded windows and the attempt, so the next load reads again."""
    _state["tried"] = False
    context.compaction.forget_windows()


def callable_models(models: Iterable[str | None]) -> set[str]:
    """Return the models that call a provider: no empty name and no rule agent."""
    return {model for model in models if model and model != gd.types.RULE_MODEL}


async def load_windows(models: Iterable[str | None]) -> None:
    """Read the provider's windows for ``models`` once per process; never raise.

    A failed read, or a model the list lacks, leaves those windows unknown, which
    ``window_of`` then answers with the backend's setting.
    """
    wanted = callable_models(models)
    if _state["tried"] or not wanted:
        return
    _state["tried"] = True
    try:
        await context.compaction.load_windows(wanted, fetcher=fetch_windows)
    except Exception as error:
        logger.info("context windows partly unknown: %s", type(error).__name__)


def window_of(model: str | None) -> int | None:
    """Return the tokens a call to ``model`` may hold, as geomind sees it.

    A rule agent calls no model, so it has none. Otherwise geomind's window comes
    first, then the backend's single setting; ``None`` when neither is known.
    """
    if model == gd.types.RULE_MODEL:
        return None
    try:
        window = context.compaction.context_window(model) if model else None
    except Exception:
        window = None
    if isinstance(window, int) and window > 0:
        return window
    return configured_window()
