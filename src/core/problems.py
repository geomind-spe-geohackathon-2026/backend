"""The shapes of what gemini's validation reports, as the contract names them."""

import ast
import re
from typing import Any

from pydantic import BaseModel

BOUNDS = re.compile(r"within the bounds (\{[^}]*\})( \(SI\))?")


class Problem(BaseModel):
    path: str
    message: str
    code: str


class Missing(BaseModel):
    path: str
    message: str


def bounds_text(bounds: dict[str, float]) -> str:
    """Return the sides of a gemini range as words."""
    lower, upper = bounds.get("min"), bounds.get("max")
    if lower is not None and upper is not None:
        return f"between {lower:g} and {upper:g}"
    return f"at least {lower:g}" if upper is None else f"at most {upper:g}"


def readable(message: str) -> str:
    """Return gemini's message with its range written in words, not as Python."""

    def replace(found: re.Match[str]) -> str:
        unit = " in SI units" if found.group(2) else ""
        return f"{bounds_text(ast.literal_eval(found.group(1)))}{unit}"

    return BOUNDS.sub(replace, message)


def problem_of(raw: dict[str, Any]) -> dict[str, str]:
    """Return gemini's problem as path, message and code; a missing path is empty."""
    return {
        "path": raw.get("path") or "",
        "message": readable(raw["message"]),
        "code": raw["code"],
    }
