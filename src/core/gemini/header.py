"""The header every gemini document carries, which a schema alone does not fix."""

from typing import Any

import gemini as gm

from src.core.gemini import case

DURATION = "duration"


def case_schema() -> dict[str, Any]:
    """Return gemini's case schema with the kind a case document must carry."""
    schema = case.schema()
    kind = {**schema["properties"]["kind"], "const": gm.Case.__name__.lower()}
    properties = {**schema["properties"], "kind": kind}
    items = schema["properties"]["requirements"]["items"]
    requirements = {
        **schema["properties"]["requirements"],
        "items": {
            **items,
            "x-roles": requirement_roles(),
            "x-time-units": time_units(),
        },
    }
    return {**schema, "properties": {**properties, "requirements": requirements}}


def time_units() -> list[str]:
    """Return the units a duration requirement is written in."""
    return list(gm.units.names(DURATION))


def requirement_roles() -> dict[str, dict[str, list[str]]]:
    """Return the quantities of each role and the units of each quantity."""
    return {
        role: {
            name: [] if item["dimension"] is None else gm.units.names(item["dimension"])
            for name, item in quantities.items()
        }
        for role, quantities in gm.plants.roles().items()
    }
