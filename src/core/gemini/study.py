"""The wrapper around gemini's study: its kinds, the inputs it misses, and its run."""

import json
from collections.abc import Callable
from typing import Any

import gemini as gm
from starlette import status

from src.core.errors import AppError, ValidationFailedError
from src.core.gemini import case
from src.core.gemini import plant as plant_document
from src.core.problems import problem_of

CASE_FILE = "case/case.json"
PLANT_FILE = "plant.json"
CASE_FOLDER = "case/"
MISSING_CODE = "missing_value"
INPUTS = frozenset({"plant", "case", "plan"})
SIZE_KIND = "size"
SIZE_DOCUMENT = {"method": "run", "prepare": [SIZE_KIND]}
PREPARE_KEY = "prepare"
METHOD_USE = "method"
PREPARE_USE = "prepare"
STUDY_TITLE = "Study"


class StudyRunError(AppError):
    """A study that gemini could not run; ``details.code`` is gemini's own code."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "study_failed"


class StudyCancelledError(Exception):
    """A study stopped between trials because its cancel flag was set."""


def reserved_keys() -> frozenset[str]:
    """Return the study keys that the backend sets itself, never taken from settings."""
    schema = gm.Study.schema()
    return frozenset(schema["required"]) | {"about"}


def with_prepare(settings: dict[str, Any], hint: str | None) -> dict[str, Any]:
    """Add the step before a method to the settings gemini lists for it."""
    prepare = gm.Study.schema()["properties"][PREPARE_KEY]
    shown = {**prepare, "title": "Before the method"}
    if hint is not None:
        shown["description"] = hint
    properties = {**settings["properties"], PREPARE_KEY: shown}
    return {**settings, "title": STUDY_TITLE, "properties": properties}


def kinds() -> list[dict[str, Any]]:
    """Return gemini's study kinds with their settings; prepare steps say so in use."""
    listed = gm.study.kinds()
    hint = next(
        (item["description"] for item in listed if item["use"] == PREPARE_USE), None
    )
    return [
        {
            "kind": item["kind"],
            "use": item["use"],
            "title": item["title"],
            "description": item["description"],
            "schema": with_prepare(item["settings"], hint)
            if item["use"] == METHOD_USE
            else {**item["settings"], "title": STUDY_TITLE},
        }
        for item in listed
    ]


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
        **(SIZE_DOCUMENT if kind == SIZE_KIND else {}),
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
    readable = [problem_of(problem) for problem in problems]
    fields = {problem["path"] or "settings": problem["message"] for problem in readable}
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
    return [problem_of(item.problem()) for item in study.check() if not item.is_warning]


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
    named = {item["path"] for item in problems}
    plant_level = [
        item
        for item in plant_document.missing_plant_values(plant_content)
        if item["path"] not in named
    ]
    return [
        {"path": item["path"], "message": item["message"]}
        for item in plant_level + problems
    ]


def progress_of(
    report: Callable[[int, int], None],
    is_cancelled: Callable[[], bool],
) -> Callable[[int, int], None]:
    """Return gemini's callback: stop a cancelled study, else report its trials."""

    def on_progress(done: int, total: int) -> None:
        if is_cancelled():
            raise gm.errors.Cancelled("The study was cancelled")
        report(done, max(done, total))

    return on_progress


def plain_day(day: dict[str, Any]) -> dict[str, Any]:
    """Return one day of gemini's coverage with its quantities as plain figures."""
    return {
        key: value if isinstance(value, str) else value.to_dict()
        for key, value in day.items()
    }


def coverage_of(outcome: Any, case_content: dict[str, Any], files: Any) -> dict:
    """Return gemini's daily coverage of a run, by service."""
    built = case.build(case_content, files)
    coverage = gm.evaluate.daily_coverage(outcome.plant, built, outcome.results)
    return {
        service: [plain_day(day) for day in days] for service, days in coverage.items()
    }


def stored_coverage(
    design: dict[str, Any],
    case_content: dict[str, Any],
    case_files: dict[str, bytes],
) -> dict[str, Any] | None:
    """Compute the coverage of a stored design again; a design that fails gives none."""
    try:
        built = case.build(case_content, case_files)
        plant = gm.Plant.from_dict(design)
        results = gm.simulate(plant, built)
        coverage = gm.evaluate.daily_coverage(plant, built, results)
    except gm.errors.GeminiError:
        return None
    return {
        service: [plain_day(day) for day in days] for service, days in coverage.items()
    }


def run(
    kind: str,
    name: str,
    settings: dict[str, Any],
    inputs: tuple[dict[str, Any], dict[str, Any], dict[str, bytes]],
    report: Callable[[int, int], None],
    is_cancelled: Callable[[], bool],
) -> dict[str, Any]:
    """Run a study of one plant on one case; return report, run, design, coverage.

    ``inputs`` is the plant document, the case document and the case's files.
    """
    plant_content, case_content, case_files = inputs
    files = files_of(plant_content, case_content, case_files)
    study = from_dict(kind, name, settings, files)
    try:
        progress = progress_of(report, is_cancelled)
        outcome = study.run(on_progress=progress).runs[0]
        return {
            "report": outcome.report.to_dict(),
            "run": outcome.to_dict(),
            "design": outcome.plant.to_dict(),
            "coverage": coverage_of(outcome, case_content, case_files),
        }
    except gm.errors.Cancelled as error:
        raise StudyCancelledError(str(error)) from error
    except gm.errors.GeminiError as error:
        raise StudyRunError(str(error), details={"code": error.code}) from error


def evolution_in(content: Any, depth: int = 0) -> dict[str, Any] | None:
    """Return the ``Evolution.to_dict()`` held somewhere in a stored study result, or ``None``.

    A study run from the page keeps it at ``run.found``; one an agent ran keeps it in its
    ``study/<name>`` artifact's ``result``. Both are found by their ``structures`` and
    ``objectives`` keys.
    """
    if not isinstance(content, dict) or depth > 5:
        return None
    if isinstance(content.get("structures"), list) and "objectives" in content:
        return content
    for value in content.values():
        if isinstance(value, dict):
            found = evolution_in(value, depth + 1)
            if found is not None:
                return found
        elif isinstance(value, list):
            for item in value[:20]:
                found = evolution_in(item, depth + 1)
                if found is not None:
                    return found
    return None


def _objective_names(objectives: list[Any]) -> list[tuple[str, int]]:
    """Return ``(metric, sign)`` of each objective; a leading ``-`` maximises, as gemini reads."""
    found = []
    for item in objectives:
        text = str(item)
        found.append((text[1:], -1) if text.startswith("-") else (text, 1))
    return found


def _value(metric: Any) -> float | None:
    if isinstance(metric, dict):
        metric = metric.get("value")
    return metric if isinstance(metric, (int, float)) else None


def _same(design: dict[str, Any], other: dict[str, Any]) -> bool:
    return design.get("structure") == other.get("structure") and design.get(
        "parameters"
    ) == other.get("parameters")


def ranked_structures(evolution: dict[str, Any], limit: int) -> dict[str, Any]:
    """Return the best design of each structure, ranked as gemini ranks, up to ``limit``.

    gemini's rule (``evolve._ordered``): the smaller total violation first (feasible is 0), then
    the first objective in its direction. A structure no simulation reached has no design and is
    left out. ``on_front`` says whether that design is on the Pareto front.
    """
    objectives = _objective_names(list(evolution.get("objectives") or []))
    front = list(evolution.get("front") or [])
    rows = []
    for item in evolution.get("structures") or []:
        best = item.get("best")
        if not isinstance(best, dict):
            continue
        rows.append((item, best))

    def key(row: tuple[dict[str, Any], dict[str, Any]]) -> tuple[float, ...]:
        _, best = row
        violation = best.get("violation") or 0.0
        keys = [float(violation)]
        for name, sign in objectives:
            value = _value((best.get("metrics") or {}).get(name))
            keys.append(sign * value if value is not None and best.get("feasible") else 0.0)
        return tuple(keys)

    rows.sort(key=key)
    structures = []
    for rank, (item, best) in enumerate(rows[:limit], start=1):
        structures.append(
            {
                "rank": rank,
                "structure": item.get("structure") or best.get("structure") or {},
                "evaluations": item.get("evaluations"),
                "feasible_evaluations": item.get("feasible"),
                "feasible": bool(best.get("feasible")),
                "reason": best.get("reason"),
                "violation": best.get("violation"),
                "metrics": best.get("metrics") or {},
                "parameters": best.get("parameters") or {},
                "on_front": any(_same(best, other) for other in front),
            }
        )
    return {
        "objectives": list(evolution.get("objectives") or []),
        "budget": evolution.get("budget") or {},
        "total": len(rows),
        "structures": structures,
    }


def stored_plant(evolution: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    """Return the stored plant of a ranked structure's design, or ``None`` when none is stored.

    ``Evolution.to_dict()`` keeps a plant only for ``best`` and the ``front``; a structure's own
    summary has none, and building it needs gemini's search space (not public).
    """
    designs = [evolution.get("best"), *(evolution.get("front") or [])]
    for design in designs:
        if isinstance(design, dict) and _same(design, row) and design.get("plant"):
            return design["plant"]
    return None
