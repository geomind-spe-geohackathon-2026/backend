import json
from typing import Any

import gemini as gm

from src.core.gemini.errors import PlantInvalidError

GEMINI_PACKAGE = "gemini"
PLANT_ERRORS = (
    gm.errors.GeminiError,
    AttributeError,
    KeyError,
    TypeError,
    ValueError,
)


def plant_invalid(message: str) -> PlantInvalidError:
    return PlantInvalidError("Plant is invalid", details={"message": message})


def resolve_plant_class(plant_type: Any) -> type[gm.modules.Module]:
    """Find the public gemini plant that a stored ``module:Class`` path names.

    Nothing is imported from the string. The class must be one that ``gm.plants``
    publishes, and only the package and class name are compared, so versions saved
    before gemini moved a file still resolve.
    """
    if not isinstance(plant_type, str):
        raise plant_invalid(f"plant_type = {plant_type!r}; expected a class path")
    module, _, name = plant_type.partition(":")
    if module.partition(".")[0] != GEMINI_PACKAGE or name not in gm.plants.__all__:
        raise plant_invalid(f"plant_type = {plant_type!r}; expected a gemini plant")
    return getattr(gm.plants, name)


def load_plant(content: dict[str, Any]) -> gm.modules.Module:
    """Build the gemini plant from stored content."""
    if not isinstance(content, dict):
        raise plant_invalid("Plant content must be a JSON object")
    plant_class = resolve_plant_class(content.get("plant_type"))
    current_type = f"{plant_class.__module__}:{plant_class.__qualname__}"
    try:
        return plant_class.from_dict({**content, "plant_type": current_type})
    except PLANT_ERRORS as error:
        raise plant_invalid(str(error)) from error


def dump_plant(plant: gm.modules.Module) -> dict[str, Any]:
    """Return the content gemini stores for a plant."""
    return plant.to_dict()


def validate_content(content: dict[str, Any]) -> dict[str, Any]:
    """Load then dump content; return it normalised, or raise plant_invalid."""
    normalised = dump_plant(load_plant(content))
    try:
        json.dumps(normalised, allow_nan=False)
    except ValueError as error:
        raise plant_invalid(str(error)) from error
    return normalised


def example_plant() -> dict[str, Any]:
    """Return the content of gemini's public doublet, without parameter values."""
    return dump_plant(gm.plants.Doublet())
