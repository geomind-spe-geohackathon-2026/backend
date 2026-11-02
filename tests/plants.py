"""Plant documents for tests, written by gemini's public templates."""

from typing import Any

import gemini as gm


def example_plant() -> dict[str, Any]:
    """Return the document of the first public heating template, as an example."""
    name = gm.plants.names("heating")[0]
    return gm.plants.get(name).to_dict()


def changed_plant(doublets: int) -> dict[str, Any]:
    """Return the example document with another doublet count, checked by gemini."""
    content = example_plant()
    content["size"]["doublets"]["value"] = doublets
    return gm.Plant.from_dict(content).to_dict()
