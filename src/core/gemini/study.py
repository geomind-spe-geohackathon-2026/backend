"""The wrapper around gemini's study: its kinds, the inputs it misses, and its run."""

import json
from typing import Any

import gemini as gm
from starlette import status

from src.core.errors import AppError, CaseInvalidError, ValidationFailedError
from src.core.gemini import plant as plant_document

CASE_FILE = "case/case.json"
PLANT_FILE = "plant.json"
CASE_FOLDER = "case/"
MISSING_CODE = "missing_value"


class StudyRunError(AppError):
    """A study that gemini could not run; ``details.code`` is gemini's own code."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "study_failed"


def reserved_keys() -> frozenset[str]:
    """Return the study keys that the backend sets itself, never taken from settings."""
    schema = gm.Study.schema()
    return frozenset(schema["required"]) | {"about"}


def kinds() -> list[dict[str, Any]]:
    """Return gemini's study methods, each with the study schema that all share."""
    schema = gm.Study.schema()
    return [
        {
            "kind": method,
            "title": method.capitalize(),
            "description": describe(method),
            "schema": schema,
        }
        for method in schema["properties"]["method"]["enum"]
    ]


def describe(method: str) -> str:
    """Return the first line of the documentation of the function behind a method."""
    function = getattr(gm.study, method, gm.Study.run)
    return (function.__doc__ or "").strip().splitlines()[0]


def document(kind: str, name: str, settings: dict[str, Any]) -> dict[str, Any]:
    """Return the study document for the case and plant files the backend gives it."""
    clashes = reserved_keys() & settings.keys()
    if clashes:
        raise ValidationFailedError(
            {key: "This key is set by the backend" for key in sorted(clashes)}
        )
    header = gm.Study.schema()["properties"]
    return {
        "format": header["format"]["const"],
        "kind": header["kind"]["const"],
        "name": name,
        "cases": [CASE_FILE],
        "plants": [PLANT_FILE],
        "method": kind,
        **settings,
    }


def files_of(
    plant_content: dict[str, Any],
    case_content: dict[str, Any],
    case_files: dict[str, bytes],
) -> dict[str, bytes]:
    """Return the files a study names, as gemini reads them from memory."""
    files = {f"{CASE_FOLDER}{name}": data for name, data in case_files.items()}
    files[CASE_FILE] = json.dumps(case_content).encode()
    files[PLANT_FILE] = json.dumps(plant_content).encode()
    return files


def validation_failed(problems: list[dict[str, Any]]) -> ValidationFailedError:
    """Return validation_failed with one field per problem gemini lists."""
    fields = {problem["path"] or "settings": problem["message"] for problem in problems}
    return ValidationFailedError(fields)


def from_dict(
    kind: str,
    name: str,
    settings: dict[str, Any],
    files: dict[str, bytes] | None = None,
) -> gm.Study:
    """Build the gemini study, or raise validation_failed for its settings."""
    try:
        return gm.Study.from_dict(document(kind, name, settings), files=files)
    except gm.errors.ValidationError as error:
        raise validation_failed(list(error.problems)) from error


def case_missing(content: dict[str, Any], files: dict[str, bytes]) -> list[dict]:
    """Return the values a case document lacks; other problems are case_invalid."""
    try:
        gm.Case.from_dict(content, files=files)
    except gm.errors.ValidationError as error:
        problems = list(error.problems)
    else:
        return []
    others = [item for item in problems if item["code"] != MISSING_CODE]
    if others:
        raise CaseInvalidError(others)
    return [{"path": item["path"], "message": item["message"]} for item in problems]


def issues_of(study: gm.Study) -> list[dict[str, Any]]:
    """Return gemini's problems for a study whose files it can read."""
    return [issue.problem() for issue in study.check()]


def missing_inputs(
    kind: str,
    name: str,
    settings: dict[str, Any],
    plant_content: dict[str, Any],
    case_content: dict[str, Any],
    case_files: dict[str, bytes],
) -> list[dict[str, str]]:
    """Return what a study lacks to run, as ``{path, message}``; empty means ready.

    Raises validation_failed for settings gemini refuses, plant_invalid or
    case_invalid for a document it refuses.
    """
    files = files_of(plant_content, case_content, case_files)
    study = from_dict(kind, name, settings, files)
    plant_document.from_dict(plant_content)
    lacking = case_missing(case_content, case_files)
    if lacking:
        return lacking
    problems = issues_of(study)
    others = [item for item in problems if item["code"] != MISSING_CODE]
    if others:
        raise validation_failed(others)
    return [{"path": item["path"], "message": item["message"]} for item in problems]


def run(
    kind: str,
    name: str,
    settings: dict[str, Any],
    plant_content: dict[str, Any],
    case_content: dict[str, Any],
    case_files: dict[str, bytes],
) -> dict[str, Any]:
    """Run a study of one plant on one case; return report, run record, design."""
    files = files_of(plant_content, case_content, case_files)
    study = from_dict(kind, name, settings, files)
    try:
        outcome = study.run().runs[0]
        return {
            "report": outcome.report.to_dict(),
            "run": outcome.to_dict(),
            "design": outcome.plant.to_dict(),
        }
    except gm.errors.GeminiError as error:
        raise StudyRunError(str(error), details={"code": error.code}) from error
