"""A small case document and its demand file, as an example for tests."""

from copy import deepcopy
from typing import Any

DEMAND_FILE = "data/example_demand.csv"
DEMAND_CSV = (
    b"time,heat\n"
    b"2030-01-01T00:00:00+00:00,1.5\n"
    b"2030-01-02T00:00:00+00:00,2\n"
    b"2030-01-03T00:00:00+00:00,2.5\n"
    b"2030-01-04T00:00:00+00:00,3\n"
)


def example_case() -> dict[str, Any]:
    """Return a case that names one demand file and sets nothing else."""
    return {
        "format": 1,
        "kind": "case",
        "name": "example",
        "time": {
            "start": "2030-01-01",
            "end": "2030-01-05",
            "step": {"value": 1, "unit": "d"},
        },
        "demand": {
            "heating": {"power": {"file": DEMAND_FILE, "column": "heat", "unit": "MW"}}
        },
    }


def broken_case() -> dict[str, Any]:
    """Return the example case with a unit gemini refuses for power."""
    content = deepcopy(example_case())
    content["demand"]["heating"]["power"]["unit"] = "K"
    return content


def site_case() -> dict[str, Any]:
    """Return a case that states the ground and the reservoir."""
    content = deepcopy(example_case())
    content["site"] = {
        "ground": {
            "gradient": {"value": 0.03, "unit": "K/m"},
            "surface_temperature": {"value": 10, "unit": "degC"},
        },
        "reservoir": {
            "permeability": {"value": 1e-13, "unit": "m2"},
            "thickness": {"value": 100, "unit": "m"},
        },
    }
    return content
