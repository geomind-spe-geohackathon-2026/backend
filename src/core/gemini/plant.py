"""The wrapper around gemini's plant document: build, write, check and describe it."""

import json
from datetime import datetime
from functools import cache
from typing import Any

import gemini as gm

from src.core.gemini.errors import PlantInvalidError, PlantModuleNotFoundError
from src.core.problems import problem_of

MISSING_CODE = "missing_value"
CASE_SECTIONS = frozenset(gm.Case.schema()["properties"])


def plant_invalid(
    problems: list[dict[str, Any]],
    message: str | None = None,
) -> PlantInvalidError:
    """Return the plant_invalid error for gemini's problems."""
    problems = [problem_of(problem) for problem in problems]
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


def problems_of(content: Any, case: gm.Case | None = None) -> list[dict[str, str]]:
    """Return the structural problems of a document, else what the case leaves."""
    try:
        plant = gm.Plant.from_dict(content)
    except gm.errors.ValidationError as error:
        return [problem_of(problem) for problem in error.problems]
    return [problem_of(issue.problem()) for issue in gm.check(plant, case)]


def from_template(name: str) -> gm.Plant:
    """Return a new plant of the named gemini plant class, or raise plant_invalid."""
    try:
        return gm.plants.get(name)
    except gm.errors.ValidationError as error:
        raise plant_invalid(list(error.problems), str(error)) from error


def case_needs(content: Any, case: gm.Case) -> list[dict[str, str]]:
    """Return the values of the case a plant still needs, from gemini's check."""
    return [
        {"path": item["path"], "message": item["message"]}
        for item in problems_of(content, case)
        if item["code"] == MISSING_CODE and item["path"].split(".")[0] in CASE_SECTIONS
    ]


def template_names() -> list[str]:
    """Return the names of gemini's plant classes."""
    return list(gm.plants.names())


def module_names(category: str | None) -> list[str]:
    """Return the names in gemini's module registry, or raise plant_invalid."""
    try:
        return list(gm.modules.names(category))
    except gm.errors.ValidationError as error:
        raise plant_invalid(list(error.problems), str(error)) from error


@cache
def describe_class(name: str) -> dict[str, Any]:
    """Return gemini's description of a registered module class."""
    return gm.modules.get(name)().describe()


def ports_of(name: str) -> dict[str, Any]:
    """Return a module class's type with its inlets and outlets and their kinds."""
    description = describe_class(name)
    return {
        "type": description["type"],
        "inlets": [
            {"port": port, "kind": declared["kind"]}
            for port, declared in description["inlets"].items()
        ],
        "outlets": [
            {"port": port, "kind": declared["kind"]}
            for port, declared in description["outlets"].items()
        ],
    }


@cache
def describe_template(name: str) -> dict[str, Any]:
    """Return a template's summary as its description, and its purpose."""
    plant = gm.plants.get(name)
    modules = structure(plant)["modules"]
    return {
        "description": plant.describe()["summary"],
        "purpose": plant.purpose,
        "modules": len(modules),
        "categories": sorted({module["category"] for module in modules}),
    }


def get_module(plant: gm.Plant, module: str) -> Any:
    """Return the module at a dotted path, or raise module_not_found."""
    try:
        return plant.get_submodule(module)
    except gm.errors.ValidationError as error:
        raise PlantModuleNotFoundError(f"Module {module} not found") from error


def port_kind(plant: gm.Plant, port: str) -> str | None:
    """Return the stream kind a port declares, as gemini describes the module."""
    module, _, name = port.rpartition(".")
    description = get_module(plant, module).describe()
    declared = {**description["inlets"], **description["outlets"]}
    return declared[name]["kind"]


def connection_of(plant: gm.Plant, connection: dict[str, Any]) -> dict[str, Any]:
    """Return a connection with its stream: own kind, else target's, else source's."""
    stream = (
        connection["kind"]
        or port_kind(plant, connection["target"])
        or port_kind(plant, connection["source"])
    )
    return {
        "source": connection["source"],
        "target": connection["target"],
        "stream": stream,
        "kind": connection["kind"],
    }


def module_ids(tree: dict[str, Any], prefix: str = "") -> list[str]:
    """Return the dotted paths of the equipment in gemini's module structure."""
    found = []
    for name, node in tree.items():
        path = f"{prefix}{name}"
        children = node.get("modules")
        if children:
            found.extend(module_ids(children, f"{path}."))
        elif node["type"] not in {"ModuleList", "ModuleDict"}:
            found.append(path)
    return found


def free_document(plant: gm.Plant) -> dict[str, Any]:
    """Return the plant as a free structure, without class type and size.

    A class-level parameter such as ``depth`` is left out: its value is already on the
    modules, and gemini refuses it on a plant without a class.
    """
    document = plant.to_dict(structure=True)
    free = {
        key: value for key, value in document.items() if key not in {"type", "size"}
    }
    free["params"] = {
        key: value
        for key, value in document["params"].items()
        if key in document["modules"]
    }
    return free


def structure(plant: gm.Plant) -> dict[str, list[dict[str, Any]]]:
    """Return the modules and connections of a plant as the flowsheet shows them."""
    modules = []
    for path in module_ids(plant.to_dict(structure=True)["modules"]):
        description = get_module(plant, path).describe()
        modules.append(
            {
                "id": path,
                "type": description["type"],
                "title": description["type"],
                "category": description["category"],
            }
        )
    connections = [
        connection_of(plant, connection)
        for connection in plant.describe()["connections"]
    ]
    return {"modules": modules, "connections": connections}


def structure_of(content: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return the modules and connections of a plant document."""
    return structure(from_dict(content))


def set_parameters(
    plant: gm.Plant,
    module: str,
    params: dict[str, Any],
    valid_from: datetime | None,
) -> None:
    """Set a module's parameters from the date given, or raise plant_invalid."""
    get_module(plant, module)
    try:
        plant.set_params(module, params, valid_from)
    except gm.errors.ValidationError as error:
        raise plant_invalid(list(error.problems), str(error)) from error


def missing_parameters(
    plant: gm.Plant,
    module: str,
    case: gm.Case | None,
) -> list[str]:
    """Return the names of the module's own parameters that the plant and case leave."""
    owner = f"params.{module}"
    return [
        issue.path.rpartition(".")[2]
        for issue in gm.check(plant, case)
        if issue.kind == "missing" and issue.path.rpartition(".")[0] == owner
    ]


def parameters(
    plant: gm.Plant,
    module: str,
    at: datetime | None,
    case: gm.Case | None,
) -> dict[str, Any]:
    """Return a module's schema, values at a time, missing names and history."""
    target = get_module(plant, module)
    return {
        "module": module,
        "type": target.describe()["type"],
        "schema": target.parameter_schema(),
        "values": plant.params_at(module, at),
        "missing": missing_parameters(plant, module, case),
        "history": plant.param_history(module),
    }
