from copy import deepcopy

import pytest

from src.core.gemini.errors import PlantInvalidError
from src.core.gemini.plant import (
    dump_plant,
    example_plant,
    load_plant,
    validate_content,
)


def assert_plant_invalid(content: object, message: str) -> None:
    with pytest.raises(PlantInvalidError) as error:
        load_plant(content)
    assert error.value.status_code == 422
    assert error.value.code == "plant_invalid"
    assert message in error.value.details["message"]


def test_example_plant_round_trips_unchanged() -> None:
    content = example_plant()

    assert dump_plant(load_plant(content)) == content


def test_plant_with_values_round_trips_unchanged() -> None:
    plant = load_plant(example_plant())
    plant.update_params(**{"esp.no_stages": 12})
    content = dump_plant(plant)

    assert content != example_plant()
    assert dump_plant(load_plant(content)) == content


def test_validate_content_returns_the_content() -> None:
    assert validate_content(example_plant()) == example_plant()


def test_stored_paths_from_before_a_gemini_move_still_load() -> None:
    content = deepcopy(example_plant())
    content["plant_type"] = "gemini.old.place:Doublet"
    for module in content["modules"].values():
        module["class"] = module["class"].replace("gemini.core.", "gemini.")

    assert dump_plant(load_plant(content)) == example_plant()


@pytest.mark.parametrize(
    "plant_type",
    [
        "os:system",
        "examples.shared.doublet_heat.plant:DoubletHeatPlant",
        "geminix.plants:Doublet",
        "Doublet",
        None,
        42,
    ],
)
def test_plant_type_outside_gemini_is_invalid(plant_type: object) -> None:
    assert_plant_invalid({**example_plant(), "plant_type": plant_type}, "plant_type")


@pytest.mark.parametrize(
    "plant_type",
    ["gemini.core.modules.pumps.esp:ESP", "gemini.core.modules.module:Module"],
)
def test_gemini_class_that_is_no_plant_is_invalid(plant_type: str) -> None:
    assert_plant_invalid({**example_plant(), "plant_type": plant_type}, "plant_type")


def test_wrong_module_paths_are_invalid() -> None:
    content = deepcopy(example_plant())
    del content["modules"]["esp"]

    assert_plant_invalid(content, "module paths")


def test_wrong_format_version_is_invalid() -> None:
    assert_plant_invalid({**example_plant(), "version": 2}, "format version")


@pytest.mark.parametrize(
    "broken",
    [{"modules": None}, {"modules": {"": "not-a-module"}}, {"modules": []}],
)
def test_malformed_modules_are_invalid(broken: dict) -> None:
    with pytest.raises(PlantInvalidError):
        load_plant({**example_plant(), **broken})


def test_bad_parameter_value_is_invalid() -> None:
    content = deepcopy(example_plant())
    content["modules"]["esp"]["params"]["no_stages"] = "many"

    with pytest.raises(PlantInvalidError):
        load_plant(content)


def test_content_that_is_no_object_is_invalid() -> None:
    assert_plant_invalid(["not", "a", "plant"], "JSON object")


def test_values_json_cannot_hold_are_invalid() -> None:
    content = deepcopy(example_plant())
    content["modules"][""]["boundary"] = {"temperature": float("nan")}

    with pytest.raises(PlantInvalidError):
        validate_content(content)
