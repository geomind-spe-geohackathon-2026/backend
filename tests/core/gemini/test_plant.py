from copy import deepcopy

import pytest

from src.core.gemini.errors import PlantInvalidError
from src.core.gemini.plant import from_dict, to_dict, validate_content
from tests.plants import changed_plant, example_plant


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
