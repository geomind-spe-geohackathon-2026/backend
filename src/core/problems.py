"""The shapes of what gemini's validation reports, as the contract names them."""

from typing import Any

from pydantic import BaseModel


class Problem(BaseModel):
    path: str
    message: str
    code: str


class Missing(BaseModel):
    path: str
    message: str


def problem_of(raw: dict[str, Any]) -> dict[str, str]:
    """Return gemini's problem as path, message and code; a missing path is empty."""
    return {
        "path": raw.get("path") or "",
        "message": raw["message"],
        "code": raw["code"],
    }
