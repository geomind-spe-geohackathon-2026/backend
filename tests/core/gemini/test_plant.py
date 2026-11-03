import json
from copy import deepcopy
from pathlib import Path

import gemini as gm
import pytest

from src.core.gemini import plant
from src.core.gemini.errors import PlantInvalidError
from src.core.gemini.plant import from_dict, to_dict, validate_content
from tests.plants import changed_plant, example_plant

EXAMPLE = Path(__file__).parents[2] / "fixtures" / "hackathon"


def assert_plant_invalid(content: object) -> PlantInvalidError:
    with pytest.raises(PlantInvalidError) as error:
        from_dict(content)
    assert error.value.status_code == 422
    assert error.value.code == "plant_invalid"
    assert error.value.details["problems"]
    return error.value


def test_example_plant_round_trips_unchanged() -> None:
    content = example_plant()

    assert to_dict(from_dict(content)) == content


def test_plant_with_changed_size_round_trips_unchanged() -> None:
    content = changed_plant(3)

    assert content != example_plant()
    assert to_dict(from_dict(content)) == content


def test_validate_content_returns_the_content() -> None:
    assert validate_content(example_plant()) == example_plant()


def test_problems_come_from_gemini_with_paths() -> None:
    content = deepcopy(example_plant())
    content["params"]["zz_unknown"] = {"value": 1}

    error = assert_plant_invalid(content)

    problem = error.details["problems"][0]
    assert problem["path"] == "params.zz_unknown"
    assert problem["code"] == "unknown_name"


def test_old_format_is_invalid() -> None:
    error = assert_plant_invalid({**example_plant(), "format": 9})

    assert error.details["problems"][0]["code"] == "old_format"


@pytest.mark.parametrize("content", [["not", "a", "plant"], None, 42, {}])
def test_content_that_is_no_plant_is_invalid(content: object) -> None:
    assert_plant_invalid(content)


def test_values_json_cannot_hold_are_invalid(monkeypatch) -> None:
    import src.core.gemini.plant as module

    document = example_plant()
    document["note"] = float("nan")
    monkeypatch.setattr(module, "to_dict", lambda _plant: document)

    with pytest.raises(PlantInvalidError):
        validate_content(example_plant())


@pytest.mark.parametrize("name", plant.template_names())
def test_the_free_document_of_a_template_builds_again(name: str) -> None:
    document = plant.free_document(gm.plants.get(name))

    assert gm.Plant.from_dict(document)


def test_the_free_document_of_the_seeded_plant_keeps_the_module_depth() -> None:
    content = json.loads((EXAMPLE / "seed_plant.json").read_text())

    document = plant.free_document(gm.Plant.from_dict(content))

    assert "depth" not in document["params"]
    assert document["params"]["d0"]["depth"]["value"] == 2500
    assert gm.Plant.from_dict(document)


def test_a_plant_names_what_it_needs_from_a_nearly_empty_case() -> None:
    content = json.loads((EXAMPLE / "seed_plant.json").read_text())
    time = json.loads((EXAMPLE / "case.json").read_text())["time"]
    case = gm.Case.from_dict({"format": 1, "kind": "case", "name": "c", "time": time})

    needs = plant.case_needs(content, case)

    assert needs[0]["path"].startswith("site.")


def doublet_settings(depths: dict[str, float]) -> dict[str, str]:
    content = json.loads((EXAMPLE / "plant.json").read_text())
    for module, depth in depths.items():
        content["params"][module]["depth"] = {"value": depth, "unit": "m"}
    modules = plant.structure_of(content)["modules"]
    return {
        item["id"]: item["settings"] for item in modules if item["type"] == "Doublet"
    }


def test_doublets_at_different_depths_have_different_settings() -> None:
    settings = doublet_settings({"d0": 2000.0, "d1": 2500.0})

    assert settings["d0"] != settings["d1"]


def test_alike_doublets_have_equal_settings() -> None:
    settings = doublet_settings({"d0": 2500.0, "d1": 2500.0})

    assert settings["d0"] == settings["d1"]


def test_a_module_lists_what_a_study_can_search() -> None:
    built = from_dict(json.loads((EXAMPLE / "seed_plant.json").read_text()))
    module = next(
        item["id"]
        for item in plant.structure(built)["modules"]
        if item["type"] == "HeatPump"
    )

    names = plant.parameters(built, module, None, None)["ranges"]

    assert names
    assert all(not name.startswith("params.") for name in names)


def test_every_module_of_a_class_lists_what_a_study_can_search() -> None:
    content = json.loads((EXAMPLE / "seed_plant.json").read_text())
    content["size"]["doublets"]["value"] = 3
    built = from_dict(content)

    first = plant.parameters(built, "d0", None, None)["ranges"]
    last = plant.parameters(built, "d2", None, None)["ranges"]

    assert first
    assert last == first
    assert "nominal_flow" in last


def test_a_group_inside_a_later_module_lists_its_names() -> None:
    content = json.loads((EXAMPLE / "seed_plant.json").read_text())
    content["size"]["doublets"]["value"] = 2
    built = from_dict(content)

    assert plant.range_names(built, "d1.reservoir")
    assert plant.range_names(built, "d1.reservoir") == plant.range_names(
        built, "d0.reservoir"
    )


def test_template_text_has_no_code_marks() -> None:
    for name in plant.template_names():
        assert "``" not in plant.describe_template(name)["description"]


def seeded() -> gm.Plant:
    content = json.loads((EXAMPLE / "seed_plant.json").read_text())
    content["size"]["doublets"]["value"] = 2
    return from_dict(content)


def test_a_range_is_set_shown_and_kept_in_the_plant_file() -> None:
    built = seeded()

    plant.set_ranges(
        built, "d1", {"nominal_flow": {"min": 60.0, "max": 200.0, "unit": "m3/h"}}
    )

    shown = plant.parameters(built, "d1", None, None)["search"]["nominal_flow"]
    assert shown["unit"] == "m3/s"
    assert shown["units"]["m3/h"] == {"min": 60.0, "max": 200.0}
    assert from_dict(plant.to_dict(built)).ranges[
        "d1.nominal_flow"
    ].min == pytest.approx(60 / 3600)


def test_both_ends_empty_removes_a_range() -> None:
    built = seeded()
    assert "d0.nominal_flow" in built.ranges

    plant.set_ranges(
        built, "d0", {"nominal_flow": {"min": None, "max": None, "unit": None}}
    )

    assert "d0.nominal_flow" not in built.ranges


def test_gemini_refuses_a_range_upside_down_in_its_own_words() -> None:
    error = pytest.raises(
        PlantInvalidError,
        plant.set_ranges,
        seeded(),
        "d0",
        {"nominal_flow": {"min": 300.0, "max": 50.0, "unit": "m3/h"}},
    ).value

    assert "above max" in str(error.details)


def test_a_value_no_study_can_search_is_refused() -> None:
    with pytest.raises(PlantInvalidError):
        plant.set_ranges(seeded(), "d0", {"no_such_value": {"min": 1.0, "max": 2.0}})


def test_a_range_on_a_value_without_units_is_kept() -> None:
    built = seeded()

    plant.set_ranges(built, "d0", {"pump_efficiency": {"min": 0.6, "max": 0.8}})

    assert "d0.pump_efficiency" in built.ranges


def test_a_range_shows_in_the_unit_of_the_value() -> None:
    built = seeded()

    shown = plant.parameters(built, "d0", None, None)["search"]["nominal_flow"]

    assert shown["unit"] == "m3/s"
    assert shown["min"] == pytest.approx(50 / 3600)
    assert shown["units"]["m3/h"] == {"min": 50.0, "max": 300.0}


def test_a_temperature_range_converts_with_its_offset() -> None:
    assert plant.converted(20.0, "degC", "K") == pytest.approx(293.15)


def test_plant_level_values_are_listed_with_their_ranges() -> None:
    search = plant.plant_search(seeded())

    assert search["size.doublets"]["value"] == 2
    assert (search["size.doublets"]["min"], search["size.doublets"]["max"]) == (1, 3)
    assert search["depth"]["unit"] == "m"


def test_plant_level_ranges_are_set_and_removed() -> None:
    built = seeded()

    plant.set_plant_ranges(
        built,
        {
            "size.doublets": {"min": 1, "max": 2, "unit": None},
            "depth": {"min": 2.1, "max": 3.2, "unit": "km"},
        },
    )

    assert plant.plant_search(built)["size.doublets"]["max"] == 2
    assert plant.plant_search(built)["depth"]["min"] == 2100

    plant.set_plant_ranges(built, {"depth": {"min": None, "max": None, "unit": None}})

    assert "depth" not in built.ranges


def test_a_plant_value_without_a_value_is_refused_in_words() -> None:
    built = seeded()

    with pytest.raises(PlantInvalidError) as error:
        plant.set_plant_ranges(built, {"nothing": {"min": 1, "max": 2, "unit": None}})

    assert "set a value first" in str(error.value.details)


def test_a_plant_level_value_is_set() -> None:
    built = plant.set_plant_values(seeded(), {"depth": {"value": 2.6, "unit": "km"}})

    shown = plant.plant_search(built)["depth"]
    assert (shown["value"], shown["unit"]) == (pytest.approx(2.6), "km")
    assert shown["min"] == pytest.approx(2.0)


def test_more_doublets_add_modules_that_ask_for_their_values() -> None:
    built = plant.set_plant_values(seeded(), {"size.doublets": {"value": 3}})

    ids = [item["id"] for item in plant.structure(built)["modules"]]
    assert "d2" in ids
    assert plant.plant_search(built)["size.doublets"]["value"] == 3


def test_fewer_doublets_drop_the_values_of_the_removed_modules() -> None:
    built = plant.set_plant_values(seeded(), {"size.doublets": {"value": 1}})

    written = plant.to_dict(built)
    assert "d0" in written["params"]
    assert "d1" not in written["params"]
    assert from_dict(written).size == {"doublets": 1}


def test_a_size_outside_the_class_is_refused_in_gemini_words() -> None:
    with pytest.raises(PlantInvalidError) as error:
        plant.set_plant_values(seeded(), {"size.doublets": {"value": 9}})

    assert "expected 1 to 3" in str(error.value.details)


def test_only_plant_level_values_are_taken() -> None:
    with pytest.raises(PlantInvalidError):
        plant.set_plant_values(seeded(), {"d0.nominal_flow": {"value": 1.0}})


def test_a_new_doublet_repeats_the_values_of_the_doublets_there() -> None:
    document = json.loads((EXAMPLE / "seed_plant.json").read_text())
    document["size"]["doublets"]["value"] = 1
    document["params"] = {
        key: item
        for key, item in document["params"].items()
        if not key.startswith(("d1", "d2"))
    }
    first = {key: item for key, item in document["params"].items() if key[:2] == "d0"}
    assert first
    built = plant.resized(plant.from_dict(document), "doublets", 2)
    params = built.to_dict()["params"]
    for key, item in first.items():
        assert params[f"d1{key[2:]}"] == item


def test_a_lost_doublet_loses_its_values() -> None:
    document = json.loads((EXAMPLE / "seed_plant.json").read_text())
    built = plant.resized(plant.from_dict(document), "doublets", 1)
    assert not any(key.startswith("d1") for key in built.to_dict()["params"])
