"""The wrapper around gemini's plant document: build, write and check it."""

import json
from typing import Any

import gemini as gm

from src.core.gemini.errors import PlantInvalidError


def plant_invalid(
    problems: list[dict[str, Any]],
    message: str | None = None,
) -> PlantInvalidError:
    """Return the plant_invalid error for gemini's problems."""
    text = message or "; ".join(problem["message"] for problem in problems)
    return PlantInvalidError(
        "Plant is invalid",
        details={"message": text, "problems": problems},
    )


def from_dict(content: Any) -> gm.Plant:
    """Build the gemini plant from a plant document, or raise plant_invalid."""
    try:
        return gm.Plant.from_dict(content)
    except gm.errors.ValidationError as error:
        raise plant_invalid(list(error.problems), str(error)) from error


def to_dict(plant: gm.Plant) -> dict[str, Any]:
    """Return the plant document gemini writes for a plant."""
    return plant.to_dict()


def validate_content(content: Any) -> dict[str, Any]:
    """Read then write a plant document; return it normalised or raise plant_invalid."""
    normalised = to_dict(from_dict(content))
    try:
        json.dumps(normalised, allow_nan=False)
    except ValueError as error:
        problem = {"path": "", "code": "invalid_value", "message": str(error)}
        raise plant_invalid([problem]) from error
    return normalised
