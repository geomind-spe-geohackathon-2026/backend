import gemini as gm
import pytest

from src.core.errors import CaseInvalidError, ValidationFailedError
from src.core.gemini import study
from src.core.gemini.errors import PlantInvalidError
from tests import design_inputs as inputs


def missing(**changes):
    arguments = {
        "kind": "run",
        "name": "s",
        "settings": {},
        "plant_content": inputs.plant_content(),
        "case_content": inputs.case_content(),
        "case_files": inputs.case_files(),
    }
    return study.missing_inputs(**{**arguments, **changes})


def test_kinds_are_the_method_values_with_the_shared_schema() -> None:
    kinds = study.kinds()

    assert [item["kind"] for item in kinds] == [
        "run",
        "minimize",
        "sample",
        "sensitivity",
        "size",
    ]
    assert all(item["schema"]["title"] == "Study" for item in kinds)
    assert all(item["description"] for item in kinds)


def properties_of(kind: str) -> dict:
    return next(item for item in study.kinds() if item["kind"] == kind)["schema"]


def test_each_kind_asks_only_for_the_settings_of_its_method() -> None:
    assert set(properties_of("minimize")["properties"]) == {
        "objective",
        "evaluations",
        "seed",
    }
    assert set(properties_of("sample")["properties"]) == {"metrics", "samples", "seed"}
    assert set(properties_of("sensitivity")["properties"]) == {"metrics"}
    assert set(properties_of("run")["properties"]) == {"prepare"}


def test_the_required_settings_are_the_arguments_without_a_default() -> None:
    assert set(properties_of("sample")["required"]) == {"metrics", "samples", "seed"}
    assert properties_of("sensitivity")["required"] == ["metrics"]
    assert properties_of("run").get("required", []) == []


def test_metrics_and_the_objective_are_choices_of_gemini_metric_names() -> None:
    sample = properties_of("sample")["properties"]
    objective = properties_of("minimize")["properties"]["objective"]

    assert "lcts" in sample["metrics"]["items"]["enum"]
    assert objective["enum"] == sample["metrics"]["items"]["enum"]


def test_ready_inputs_miss_nothing() -> None:
    assert missing() == []


def test_case_files_that_are_absent_are_missing() -> None:
    found = missing(case_files={})

    assert found[0]["path"] == "demand.heating.power.file"


def test_unset_plant_values_are_missing() -> None:
    import gemini as gm

    template = gm.plants.get("HeatingPlant").to_dict()

    found = missing(plant_content=template)

    assert any(item["path"].startswith("params.") for item in found)


def test_settings_gemini_refuses_are_validation_failed() -> None:
    with pytest.raises(ValidationFailedError) as error:
        missing(kind="sample", settings={"metrics": ["lcts"]})

    assert "samples" in error.value.details["fields"]


def test_keys_the_backend_sets_are_refused() -> None:
    with pytest.raises(ValidationFailedError) as error:
        missing(settings={"cases": ["x.json"]})

    assert list(error.value.details["fields"]) == ["cases"]


def test_a_broken_case_is_case_invalid() -> None:
    content = inputs.case_content()
    content["demand"] = {"heating": {"power": {"value": 5, "unit": "m"}}}

    with pytest.raises(CaseInvalidError):
        missing(case_content=content)


def test_a_broken_plant_is_plant_invalid() -> None:
    content = inputs.plant_content()
    content["params"]["zz_unknown"] = {"value": 1}

    with pytest.raises(PlantInvalidError):
        missing(plant_content=content)


def test_a_run_gives_report_run_and_design() -> None:
    outcome = study.run(
        "run",
        "s",
        {},
        inputs.plant_content(),
        inputs.case_content(),
        inputs.case_files(),
    )

    assert outcome["report"]["lcts"]["unit"] == "EUR/MWh"
    assert outcome["run"]["case_name"]
    assert outcome["design"]["kind"] == "plant"


def test_size_is_a_run_that_prepares_the_plant_and_takes_no_settings() -> None:
    assert properties_of("size")["properties"] == {}
    found = study.document("size", "s", {})

    assert (found["method"], found["prepare"]) == ("run", ["size"])
    assert "prepare" not in study.document("run", "s", {})


def test_size_refuses_a_prepare_of_its_own() -> None:
    with pytest.raises(ValidationFailedError) as error:
        study.document("size", "s", {"prepare": []})

    assert list(error.value.details["fields"]) == ["prepare"]


def test_metric_names_are_the_names_of_gemini_metrics() -> None:
    assert study.metric_names() == [item["name"] for item in gm.evaluate.metrics()]


def run_example(on_progress=None) -> dict:
    return study.run(
        "run",
        "s",
        {},
        inputs.plant_content(),
        inputs.case_content(),
        inputs.case_files(),
        on_progress,
    )


def test_a_run_reports_progress_and_gives_the_daily_coverage() -> None:
    reached = []

    outcome = run_example(lambda done, total: reached.append((done, total)))

    assert reached[-1][0] == reached[-1][1]
    days = outcome["coverage"]
    assert len(days) == 365
    first = days[0]
    assert first["service"] == "heating"
    assert first["source"] in {"geothermal", "backup", "short"}
    assert len(first["date"]) == len("2027-01-01")
    assert first["demand"]["unit"] == "MWh"
    assert isinstance(first["demand"]["value"], float)
    assert isinstance(first["failed_steps"], int)


def test_cancelling_from_the_callback_stops_the_study() -> None:
    def stop(done: int, total: int) -> None:
        raise study.StudyCancelled("stop")

    with pytest.raises(study.StudyCancelled):
        run_example(stop)
