"""The wrapper around gemini's plant document: build, write, check and describe it."""

import hashlib
import json
from datetime import datetime
from functools import cache
from typing import Any

import gemini as gm

from src.core.gemini.errors import PlantInvalidError, PlantModuleNotFoundError
from src.core.problems import problem_of

MISSING_CODE = "missing_value"
CASE_SECTIONS = frozenset(gm.Case.schema()["properties"])
UNIT_DIGITS = 10
PARAMS_PREFIX = "params."
SIZE_PREFIX = "size."


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
    return [
        problem_of(issue.problem())
        for issue in gm.check(plant, case)
        if not issue.is_warning
    ]


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


def plain_text(text: str) -> str:
    """Return gemini's text without the marks of its code words."""
    return text.replace("``", "")


@cache
def describe_template(name: str) -> dict[str, Any]:
    """Return a template's summary as its description, and its purpose."""
    plant = gm.plants.get(name)
    modules = structure(plant)["modules"]
    return {
        "description": plain_text(plant.describe()["summary"]),
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


def type_of(content: dict[str, Any]) -> str:
    """Return the class of a plant document; a free plant has its name."""
    return str(content.get("type") or content.get("name") or "Plant")


def settings_of(plant: gm.Plant, module: str, params: dict[str, Any]) -> str:
    """Return a digest of a module's values, equal only for equal settings."""
    values = get_module(plant, module).describe()["values"]
    text = json.dumps([values, params.get(module)], sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def structure_of(content: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return a plant document's modules, with a settings digest, and connections."""
    plant = from_dict(content)
    found = structure(plant)
    params = plant.to_dict()["params"]
    for module in found["modules"]:
        module["settings"] = settings_of(plant, module["id"], params)
    return found


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


@cache
def range_paths(kind: str) -> tuple[str, ...]:
    """Return the paths of a plant class that a study can search over a range."""
    found = gm.plants.capabilities().get(kind, {})
    return tuple(found.get("ranges", ()))


def owner_of(module: str, modules: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the plant module a path is, or sits inside; a module id may have dots."""
    owners = [
        item
        for item in modules
        if module == item["id"] or module.startswith(f"{item['id']}.")
    ]
    return max(owners, key=lambda item: len(item["id"]), default=None)


def range_names(plant: gm.Plant, module: str) -> list[str]:
    """Return the names under a module that a study can search over a range.

    gemini lists the paths of each class at its smallest size, so ``d1`` is not there
    while ``d0`` is, and modules of one class share what can be searched.
    """
    modules = structure(plant)["modules"]
    owner = owner_of(module, modules)
    if owner is None:
        return []
    inner = module.removeprefix(owner["id"])
    twins = [item["id"] for item in modules if item["type"] == owner["type"]]
    prefixes = tuple(f"params.{twin}{inner}." for twin in twins)
    paths = range_paths(str(plant.to_dict().get("type")))
    names = (
        path.removeprefix(prefix)
        for path in paths
        for prefix in prefixes
        if path.startswith(prefix)
    )
    return list(dict.fromkeys(names))


def leaf_at(document: dict[str, Any], path: str) -> dict[str, Any] | None:
    """Return the leaf of a plant file at a dotted path, or None without a value."""
    found: Any = document
    for part in path.split("."):
        found = found.get(part) if isinstance(found, dict) else None
    return found if isinstance(found, dict) and "value" in found else None


def converted(value: float | None, unit: str | None, target: str) -> float | None:
    """Return a number in another unit by gemini's units, without float noise."""
    if value is None or unit is None or unit == target:
        return value
    return float(f"{gm.units.Quantity(value, unit).to(target).value:.{UNIT_DIGITS}g}")


def units_of(schema: dict[str, Any]) -> list[str]:
    """Return the units a parameter's schema takes, the unit it shows in first."""
    variants = schema.get("anyOf", [])
    quantity = next((item for item in variants if "properties" in item), {})
    listed = quantity.get("properties", {}).get("unit", {}).get("enum", [])
    shown = schema.get("unit")
    return list(dict.fromkeys([*([shown] if shown else []), *listed]))


def limits_of(leaf: dict[str, Any], units: list[str]) -> dict[str, Any]:
    """Return a leaf's range in the unit it shows in and in each other unit."""
    stated = leaf.get("unit")
    limits = leaf.get("range") or {}
    low, high = limits.get("min"), limits.get("max")
    shown = units[0] if units else stated
    return {
        "min": converted(low, stated, shown) if shown else low,
        "max": converted(high, stated, shown) if shown else high,
        "unit": shown,
        "units": {
            unit: {
                "min": converted(low, stated, unit),
                "max": converted(high, stated, unit),
            }
            for unit in units
        },
    }


def search_of(plant: gm.Plant, module: str) -> dict[str, dict[str, Any]]:
    """Return the search range of what a study can search under a module."""
    params = plant.to_dict()["params"]
    schema = get_module(plant, module).parameter_schema()["properties"]
    found = {}
    for name in range_names(plant, module):
        leaf = leaf_at(params, f"{module}.{name}")
        if leaf is not None:
            found[name] = limits_of(leaf, units_of(schema.get(name, {})))
    return found


def plant_paths(plant: gm.Plant) -> list[str]:
    """Return what a study can search that no module holds, as plant file paths."""
    modules = structure(plant)["modules"]
    paths = range_paths(str(plant.to_dict().get("type")))
    named = [path.removeprefix(PARAMS_PREFIX) for path in paths]
    return [path for path in named if owner_of(path, modules) is None]


def plant_search(plant: gm.Plant) -> dict[str, dict[str, Any]]:
    """Return every plant-level search value: its value and range, or no value yet."""
    document = plant.to_dict()
    found = {}
    for path in plant_paths(plant):
        place = path if path.startswith(SIZE_PREFIX) else f"params.{path}"
        leaf = leaf_at(document, place)
        limits = limits_of(
            leaf or {}, [leaf["unit"]] if leaf and leaf.get("unit") else []
        )
        found[path] = {**limits, "value": None if leaf is None else leaf["value"]}
    return found


def bound_of(value: float | None, unit: str | None) -> Any:
    """Return one end of a range as gemini takes it: a quantity, or a plain number."""
    if value is None or unit is None:
        return value
    return gm.units.Quantity(value, unit)


def whole(value: Any) -> Any:
    """Return a count as gemini reads it: a whole number, if it is one."""
    return int(value) if isinstance(value, float) and value.is_integer() else value


def apply_range(plant: gm.Plant, path: str, limits: dict[str, Any]) -> None:
    """Set one search range with gemini's checks; both ends empty removes it."""
    unit = limits.get("unit")
    low, high = bound_of(limits["min"], unit), bound_of(limits["max"], unit)
    if path.startswith(SIZE_PREFIX):
        low, high = whole(low), whole(high)
    try:
        plant.set_range(path, low, high)
    except gm.errors.ValidationError as error:
        raise plant_invalid(list(error.problems), str(error)) from error


def set_ranges(plant: gm.Plant, module: str, ranges: dict[str, dict[str, Any]]) -> None:
    """Set the search ranges of a module, each with the unit it was typed in."""
    search = search_of(plant, module)
    for name, limits in ranges.items():
        if name not in search:
            message = f"{module}.{name}: set a value first to allow a range"
            raise plant_invalid([], message)
        apply_range(plant, f"{module}.{name}", limits)


def top_modules(plant: gm.Plant) -> set[str]:
    """Return the first part of every module path of a plant."""
    return {item["id"].split(".")[0] for item in structure(plant)["modules"]}


def resized(plant: gm.Plant, name: str, count: int) -> gm.Plant:
    """Return the plant at a new size, without values of the modules it lost."""
    document = plant.to_dict()
    document["size"][name] = {**document["size"][name], "value": count}
    gone = top_modules(plant) - top_modules(from_dict({**document, "params": {}}))
    params = {key: item for key, item in document["params"].items() if key not in gone}
    return from_dict({**document, "params": params})


def set_plant_value(plant: gm.Plant, path: str, value: float, unit: str | None) -> None:
    """Set a plant-level value that gemini keeps as a parameter."""
    module, _, name = path.rpartition(".")
    given = bound_of(value, unit)
    try:
        plant.set_params(module or None, {name: given})
    except gm.errors.ValidationError as error:
        raise plant_invalid(list(error.problems), str(error)) from error


def set_plant_values(plant: gm.Plant, values: dict[str, dict[str, Any]]) -> gm.Plant:
    """Return the plant with its plant-level values set, a size last, as it rebuilds."""
    known = plant_paths(plant)
    for path in values:
        if path not in known:
            raise plant_invalid([], f"{path}: this is not a plant-level value")
    sizes = {
        path: item for path, item in values.items() if path.startswith(SIZE_PREFIX)
    }
    for path, item in values.items():
        if path not in sizes:
            set_plant_value(plant, path, item["value"], item.get("unit"))
    for path, item in sizes.items():
        plant = resized(plant, path.removeprefix(SIZE_PREFIX), int(item["value"]))
    return plant


def set_plant_ranges(plant: gm.Plant, ranges: dict[str, dict[str, Any]]) -> None:
    """Set the search ranges that no module holds."""
    search = plant_search(plant)
    for path, limits in ranges.items():
        if search.get(path, {}).get("value") is None:
            raise plant_invalid([], f"{path}: set a value first to allow a range")
        apply_range(plant, path, limits)


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
        "ranges": range_names(plant, module),
        "search": search_of(plant, module),
        "history": plant.param_history(module),
    }
