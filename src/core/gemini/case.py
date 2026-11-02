"""The wrapper around gemini's case document: schema, validation and series."""

from typing import Any

import gemini as gm

from src.core.errors import CaseInvalidError, MissingInputsError
from src.core.problems import problem_of

MISSING_CODE = "missing_value"


def schema() -> dict[str, Any]:
    """Return gemini's JSON schema of a case, with the units of its values."""
    return gm.Case.schema()


def split(
    problems: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split problems into the missing values and the structural problems."""
    missing = [problem for problem in problems if problem["code"] == MISSING_CODE]
    structural = [problem for problem in problems if problem["code"] != MISSING_CODE]
    return missing, structural


def read(
    content: Any,
    files: dict[str, bytes] | None,
) -> tuple[gm.Case | None, list[dict[str, str]]]:
    """Build the case with the files it names; return it, or None with every problem."""
    try:
        return gm.Case.from_dict(content, files=files), []
    except gm.errors.ValidationError as error:
        return None, [problem_of(problem) for problem in error.problems]


def build(content: Any, files: dict[str, bytes] | None) -> gm.Case | None:
    """Return the case a complete document makes, else None."""
    return read(content, files)[0]


def validate(
    content: Any,
    files: dict[str, bytes] | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return the missing values and the structural problems of a case document."""
    _, problems = read(content, files)
    return split(problems)


def missing_values(
    content: Any,
    files: dict[str, bytes] | None,
) -> list[dict[str, str]]:
    """Return the values a case lacks as ``{path, message}``; else case_invalid."""
    missing, structural = validate(content, files)
    if structural:
        raise CaseInvalidError(structural)
    return [{"path": item["path"], "message": item["message"]} for item in missing]


def ensure_complete(
    content: Any,
    files: dict[str, bytes] | None,
) -> gm.Case:
    """Build the case, or raise case_invalid (structure) or missing_inputs (values)."""
    case, problems = read(content, files)
    if case is not None:
        return case
    missing, structural = split(problems)
    if structural:
        raise CaseInvalidError(structural)
    raise MissingInputsError(
        [{"path": item["path"], "message": item["message"]} for item in missing]
    )


def series_paths(node: Any, prefix: str = "") -> list[str]:
    """Return the dotted paths of the time series a case document refers to by file."""
    if not isinstance(node, dict):
        return []
    if "file" in node and "column" in node:
        return [prefix]
    found = []
    for name, child in node.items():
        found.extend(series_paths(child, f"{prefix}.{name}" if prefix else name))
    return found


def series(case: gm.Case, content: Any) -> list[dict[str, Any]]:
    """Return each series of the case as name, unit and [time, value] points."""
    result = []
    for path in series_paths(content):
        leaf = case.leaf(path).series
        points = [
            [time.isoformat(), float(value)]
            for time, value in zip(leaf.time, leaf.values, strict=True)
        ]
        result.append({"name": path, "unit": leaf.unit, "points": points})
    return result
