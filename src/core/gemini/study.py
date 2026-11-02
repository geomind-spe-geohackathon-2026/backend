"""The wrapper around gemini's study: its kinds, the inputs it misses, and its run."""

import inspect
import json
from collections.abc import Callable
from typing import Any

import gemini as gm
from starlette import status

from src.core.errors import AppError, ValidationFailedError
from src.core.gemini import case
from src.core.gemini import plant as plant_document

CASE_FILE = "case/case.json"
PLANT_FILE = "plant.json"
CASE_FOLDER = "case/"
MISSING_CODE = "missing_value"
INPUTS = frozenset({"plant", "case", "plan"})
METHODS_WITH_ARGUMENTS = ("minimize", "sample", "sensitivity")
SIZE = "size"
SIZE_METHOD = "run"
SIZE_PREPARE = ["size"]


class StudyRunError(AppError):
    """A study that gemini could not run; ``details.code`` is gemini's own code."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "study_failed"


class StudyCancelled(AppError):
    """A study stopped between two trials because its cancel flag was set."""

    status_code = status.HTTP_409_CONFLICT
    code = "cancelled"


def reserved_keys() -> frozenset[str]:
    """Return the study keys that the backend sets itself, never taken from settings."""
    schema = gm.Study.schema()
    return frozenset(schema["required"]) | {"about"}


def method_arguments(method: str) -> list[inspect.Parameter]:
    """Return the settings a gemini study function takes beyond its inputs."""
    function = getattr(gm.study, method, None)
    if function is None:
        return []
    return [
        parameter
        for name, parameter in inspect.signature(function).parameters.items()
        if name not in INPUTS and parameter.kind is not parameter.KEYWORD_ONLY
    ]


def settings_schema(method: str, full: dict[str, Any]) -> dict[str, Any]:
    """Return the schema of the settings of one method, with metric names as choices."""
    if method == SIZE:
        return {**{k: v for k, v in full.items() if k != "required"}, "properties": {}}
    reserved = reserved_keys()
    arguments = method_arguments(method)
    taken = {name for other in METHODS_WITH_ARGUMENTS for name in argument_names(other)}
    names = [parameter.name for parameter in arguments] or [
        key for key in full["properties"] if key not in reserved | taken
    ]
    properties = {
        key: with_choices(key, full["properties"][key])
        for key in names
        if key in full["properties"]
    }
    required = [
        parameter.name
        for parameter in arguments
        if parameter.default is parameter.empty and parameter.name in properties
    ]
    schema = {key: value for key, value in full.items() if key != "required"}
    return {
        **schema,
        "properties": properties,
        **({"required": required} if required else {}),
    }


def argument_names(method: str) -> list[str]:
    return [parameter.name for parameter in method_arguments(method)]


def metric_names() -> list[str]:
    """Return the metrics gemini can read from a run."""
    return [item["name"] for item in gm.evaluate.metrics()]


def with_choices(key: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Make the metric settings choices of gemini's metric names."""
    if key == "objective":
        return {**schema, "enum": metric_names()}
    if key == "metrics":
        return {**schema, "items": {**schema["items"], "enum": metric_names()}}
    return schema


def kinds() -> list[dict[str, Any]]:
    """Return gemini's study methods, each with the settings schema it takes."""
    full = gm.Study.schema()
    return [
        {
            "kind": method,
            "title": method.capitalize(),
            "description": describe(method),
            "schema": settings_schema(method, full),
        }
        for method in [*full["properties"]["method"]["enum"], SIZE]
    ]


def describe(method: str) -> str:
    """Return the first line of the documentation of the function behind a method."""
    function = getattr(gm.study, method, gm.Study.run)
    return (function.__doc__ or "").strip().splitlines()[0]


def document(kind: str, name: str, settings: dict[str, Any]) -> dict[str, Any]:
    """Return the study document for the case and plant files the backend gives it."""
    sized = kind == SIZE
    clashes = (reserved_keys() | ({"prepare"} if sized else set())) & settings.keys()
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
        "method": SIZE_METHOD if sized else kind,
        **({"prepare": SIZE_PREPARE} if sized else {}),
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
    lacking = case.missing_values(case_content, case_files)
    if lacking:
        return lacking
    problems = issues_of(study)
    others = [item for item in problems if item["code"] != MISSING_CODE]
    if others:
        raise validation_failed(others)
    return [{"path": item["path"], "message": item["message"]} for item in problems]


def coverage_of(
    design: gm.Plant,
    case_content: dict[str, Any],
    case_files: dict[str, bytes],
    results: Any,
) -> list[dict[str, Any]] | None:
    """Return the days of the run by service, flat, each with its ``service``.

    ``None`` when gemini cannot read the coverage from the run.
    """
    try:
        case_object = gm.Case.from_dict(case_content, files=case_files)
        days = gm.evaluate.daily_coverage(design, case_object, results)
    except gm.errors.GeminiError:
        return None
    return [
        plain_day(service, day) for service, found in days.items() for day in found
    ] or None


def plain_day(service: str, day: dict[str, Any]) -> dict[str, Any]:
    """Return one day of ``daily_coverage`` as JSON: energies as ``{value, unit}``."""
    energies = ("demand", "geothermal", "backup", "short")
    return {
        "date": day["date"],
        "source": day["source"],
        "service": service,
        **{key: plain_quantity(day[key]) for key in energies},
        "failed_steps": int(day["failed_steps"].value),
    }


def plain_quantity(quantity: Any) -> dict[str, Any]:
    """Return a gemini quantity as ``{value, unit}``."""
    return {"value": quantity.value, "unit": quantity.unit.value}


def run(
    kind: str,
    name: str,
    settings: dict[str, Any],
    plant_content: dict[str, Any],
    case_content: dict[str, Any],
    case_files: dict[str, bytes],
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Run a study of one plant on one case; return report, run record, design.

    ``on_progress(done, total)`` is called after each trial; raising
    ``StudyCancelled`` from it stops the study and raises it again from here.
    """
    files = files_of(plant_content, case_content, case_files)
    study = from_dict(kind, name, settings, files)
    try:
        outcome = study.run(on_progress=stoppable(on_progress)).runs[0]
        return {
            "report": outcome.report.to_dict(),
            "run": outcome.to_dict(),
            "design": outcome.plant.to_dict(),
            "coverage": coverage_of(
                outcome.plant, case_content, case_files, outcome.results
            ),
        }
    except gm.errors.Cancelled as error:
        raise StudyCancelled("Study was cancelled") from error
    except gm.errors.GeminiError as error:
        raise StudyRunError(str(error), details={"code": error.code}) from error


def stoppable(
    on_progress: Callable[[int, int], None] | None,
) -> Callable[[int, int], None] | None:
    """Wrap the callback so that ``StudyCancelled`` stops gemini the way it expects."""
    if on_progress is None:
        return None

    def callback(done: int, total: int) -> None:
        try:
            on_progress(done, total)
        except StudyCancelled as error:
            raise gm.errors.Cancelled(error.message) from error

    return callback
