import pytest

from src.core.errors import CaseInvalidError, MissingInputsError
from src.core.gemini import case, header
from tests.cases import DEMAND_CSV, DEMAND_FILE, broken_case, example_case

FILES = {DEMAND_FILE: DEMAND_CSV}


def test_schema_is_geminis_with_units() -> None:
    schema = case.schema()

    assert schema["title"] == "Case"
    assert "demand" in schema["properties"]


def test_complete_case_has_no_problems() -> None:
    assert case.validate(example_case(), FILES) == ([], [])


def test_missing_file_is_missing_not_structural() -> None:
    missing, problems = case.validate(example_case(), None)

    assert problems == []
    assert [item["path"] for item in missing] == ["demand.heating.power.file"]
    assert set(missing[0]) == {"path", "message", "code"}


def test_wrong_unit_is_structural() -> None:
    missing, problems = case.validate(broken_case(), FILES)

    assert missing == []
    assert [item["code"] for item in problems] == ["invalid_unit"]


def test_not_an_object_is_structural() -> None:
    _, problems = case.validate([], None)

    assert problems[0]["code"] == "invalid_value"


def test_ensure_complete_builds_the_case() -> None:
    assert case.ensure_complete(example_case(), FILES) is not None


def test_ensure_complete_refuses_structure_as_case_invalid() -> None:
    with pytest.raises(CaseInvalidError) as error:
        case.ensure_complete(broken_case(), FILES)

    assert error.value.details["problems"][0]["code"] == "invalid_unit"


def test_ensure_complete_refuses_missing_values_as_missing_inputs() -> None:
    with pytest.raises(MissingInputsError) as error:
        case.ensure_complete(example_case(), None)

    assert error.value.details["missing"] == [
        {
            "path": "demand.heating.power.file",
            "message": error.value.details["missing"][0]["message"],
        }
    ]


def test_series_paths_find_every_file_reference() -> None:
    content = example_case()
    content["demand"]["cooling"] = {
        "power": {"file": DEMAND_FILE, "column": "heat", "unit": "MW"}
    }

    assert case.series_paths(content) == [
        "demand.heating.power",
        "demand.cooling.power",
    ]


def test_series_gives_time_value_points_in_the_file_unit() -> None:
    content = example_case()

    series = case.series(case.ensure_complete(content, FILES), content)

    assert series == [
        {
            "name": "demand.heating.power",
            "unit": "MW",
            "points": [
                ["2030-01-01T00:00:00+00:00", 1.5],
                ["2030-01-02T00:00:00+00:00", 2.0],
                ["2030-01-03T00:00:00+00:00", 2.5],
                ["2030-01-04T00:00:00+00:00", 3.0],
            ],
        }
    ]


def test_a_new_case_lists_everything_in_time_not_just_time() -> None:
    missing, _ = case.validate({"format": 1, "kind": "case", "name": "c"}, {})

    assert {"time.start", "time.end", "time.step"} <= {item["path"] for item in missing}


def test_the_case_schema_marks_the_ends_of_time_as_dates() -> None:
    time = header.case_schema()["properties"]["time"]["properties"]

    assert time["start"]["x-date"] is True
    assert time["end"]["x-date"] is True
    assert "x-date" not in time["step"]
