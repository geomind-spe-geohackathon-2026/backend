from copy import deepcopy
from datetime import UTC, datetime

import gemini as gm
import pytest

from src.core.gemini import plant
from src.core.gemini.errors import PlantInvalidError, PlantModuleNotFoundError
from tests.plants import example_plant

MODULE = "heat_exchanger"
QUANTITY = {"thermal_conductance": {"value": 5, "unit": "W/K"}}


def test_problems_of_a_good_structure_are_its_missing_values() -> None:
    problems = plant.problems_of(example_plant())

    assert problems
    assert {problem["code"] for problem in problems} == {"missing_value"}


def test_problems_of_a_bad_structure_are_geminis_with_paths() -> None:
    content = deepcopy(example_plant())
    content["params"]["zz_unknown"] = {"value": 1}

    problems = plant.problems_of(content)

    assert [problem["code"] for problem in problems] == ["unknown_name"]
    assert problems[0]["path"].endswith("zz_unknown")


def test_plant_invalid_gives_problems_a_path_even_when_gemini_has_none() -> None:
    error = plant.plant_invalid([{"path": None, "message": "m", "code": "c"}])

    assert error.details["problems"] == [{"path": "", "message": "m", "code": "c"}]


def test_template_names_are_geminis() -> None:
    assert plant.template_names() == gm.plants.names()


def test_template_card_has_description_and_purpose() -> None:
    name = gm.plants.names("heating")[0]

    card = plant.describe_template(name)

    assert card["purpose"] == "heating"
    assert card["description"]


def test_from_template_builds_a_new_plant() -> None:
    name = gm.plants.names("heating")[0]

    assert plant.to_dict(plant.from_template(name))["type"] == name


def test_from_template_refuses_an_unknown_name() -> None:
    with pytest.raises(PlantInvalidError):
        plant.from_template("Nope")


def test_module_names_by_category() -> None:
    category = gm.modules.categories()[0]

    names = plant.module_names(category)

    assert names == gm.modules.names(category)


def test_module_names_refuse_an_unknown_category() -> None:
    with pytest.raises(PlantInvalidError):
        plant.module_names("zz")


def test_describe_class_has_type_category_and_summary() -> None:
    card = plant.describe_class("HeatExchanger")

    assert card["type"] == "HeatExchanger"
    assert card["category"] == "exchangers"
    assert card["summary"]


def test_get_module_refuses_an_unknown_path() -> None:
    built = plant.from_dict(example_plant())

    with pytest.raises(PlantModuleNotFoundError):
        plant.get_module(built, "zz")


def test_structure_lists_modules_and_connections_with_streams() -> None:
    built = plant.from_dict(example_plant())

    structure = plant.structure(built)

    ids = {module["id"] for module in structure["modules"]}
    assert MODULE in ids
    assert "filters" not in ids and "filters.hot" in ids
    assert {"gas", "brine"} <= {c["stream"] for c in structure["connections"]}
    assert all(
        set(c) == {"source", "target", "stream", "kind"}
        for c in structure["connections"]
    )


def test_port_kind_reads_the_declared_stream() -> None:
    built = plant.from_dict(example_plant())

    assert plant.port_kind(built, "gas_grid.gas_out") == "gas"


def test_set_parameters_changes_the_document() -> None:
    built = plant.from_dict(example_plant())

    plant.set_parameters(built, MODULE, QUANTITY, None)

    value = plant.to_dict(built)["params"][MODULE]["thermal_conductance"]["value"]
    assert value == 5


def test_set_parameters_refuses_a_wrong_unit() -> None:
    built = plant.from_dict(example_plant())
    wrong = {"thermal_conductance": {"value": 5, "unit": "m"}}

    with pytest.raises(PlantInvalidError) as error:
        plant.set_parameters(built, MODULE, wrong, None)

    assert error.value.details["problems"][0]["code"] == "invalid_unit"


def test_parameters_view_has_schema_values_missing_and_history() -> None:
    built = plant.from_dict(example_plant())
    plant.set_parameters(built, MODULE, QUANTITY, None)
    later = {"thermal_conductance": {"value": 7, "unit": "W/K"}}
    plant.set_parameters(built, MODULE, later, datetime(2030, 1, 1, tzinfo=UTC))

    view = plant.parameters(built, MODULE, None)

    assert view["module"] == MODULE
    assert view["type"] == "HeatExchanger"
    assert view["values"]["thermal_conductance"] == 7
    assert "thermal_conductance" not in view["missing"]
    assert "arrangement" in view["missing"]
    assert view["schema"]["properties"]["thermal_conductance"]["unit"] == "W/K"
    assert len(view["history"]) == 2


def test_missing_parameters_are_the_modules_own_only() -> None:
    built = plant.from_dict(example_plant())

    assert all("." not in name for name in plant.missing_parameters(built, MODULE))
