"""A ready case and plant for study tests, copied from gemini's example folder."""

import json
from pathlib import Path
from typing import Any

import gemini as gm

EXAMPLE = Path(__file__).parent / "fixtures" / "hackathon"


def case_content() -> dict[str, Any]:
    """Return the example case document as gemini writes it."""
    return gm.Case.from_json(EXAMPLE / "case.json").to_dict()


def case_files() -> dict[str, bytes]:
    """Return the files the example case names."""
    return gm.Case.from_json(EXAMPLE / "case.json").files()


def plant_content() -> dict[str, Any]:
    """Return the example heating plant document, with every value set."""
    return json.loads((EXAMPLE / "plant.json").read_text())


def outcome() -> dict[str, Any]:
    """Return a stored run of the example, so that tests need not run gemini."""
    return json.loads((EXAMPLE / "outcome.json").read_text())
