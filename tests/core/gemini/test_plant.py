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
