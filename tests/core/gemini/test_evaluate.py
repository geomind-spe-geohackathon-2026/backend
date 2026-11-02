import pytest

from src.core.errors import ValidationFailedError
from src.core.gemini import evaluate
from tests import design_inputs as inputs


def test_summary_counts_checks_and_lists_figures() -> None:
    parts = evaluate.summarise(inputs.outcome()["report"])

    names = [kpi["name"] for kpi in parts["summary"]["kpis"]]
    assert {"heat_delivered", "capex", "lcts", "co2"} <= set(names)
    assert "capacities" not in names
    assert parts["summary"]["checks"] == {"passed": 13, "failed": 0, "not_assessed": 2}


def test_a_missing_figure_keeps_none() -> None:
    parts = evaluate.summarise(inputs.outcome()["report"])

    cold = next(k for k in parts["summary"]["kpis"] if k["name"] == "cold_delivered")
    assert cold["value"] is None


def test_constraints_have_status_and_message() -> None:
    parts = evaluate.summarise(inputs.outcome()["report"])

    first = parts["constraints"][0]
    assert first["status"] == "pass"
    assert "against the limit" in first["message"]
    assert {"not_assessed"} <= {item["status"] for item in parts["constraints"]}


def test_failed_requirement_is_fail() -> None:
    report = inputs.outcome()["report"]
    report["requirements"][0]["passed"] = False

    assert evaluate.checks_of(report)["failed"] == 1


def feasible(lcts: float, co2: float) -> dict:
    return {
        "lcts": {"value": lcts, "unit": "EUR/MWh"},
        "co2": {"value": co2, "unit": "kt"},
        "verdict": {"feasible": True, "reasons": []},
    }


def test_pareto_flags_the_non_dominated() -> None:
    reports = [feasible(40, 20), feasible(60, 5), feasible(70, 25)]

    assert evaluate.pareto_flags(reports, "lcts", "co2") == [True, True, False]


def test_pareto_refuses_a_figure_no_report_has() -> None:
    with pytest.raises(ValidationFailedError):
        evaluate.pareto_flags([feasible(1, 1)], "nope", "co2")


def constraint(report: dict, name: str) -> dict:
    parts = evaluate.summarise(report)
    return next(item for item in parts["constraints"] if item["name"].endswith(name))


def test_a_dimensionless_figure_has_no_unit() -> None:
    item = constraint(inputs.outcome()["report"], "pump_efficiency")

    assert item["message"] == "0.7 against the limit 0.7"


def test_a_constraint_without_a_subject_has_a_clean_title_and_name() -> None:
    report = inputs.outcome()["report"]
    report["requirements"][0]["unit_path"] = ""
    report["requirements"][1]["unit_path"] = None

    items = evaluate.summarise(report)["constraints"][:2]

    assert [item["title"] for item in items] == [
        "Production flow range",
        "Production flow range",
    ]
    assert [item["name"] for item in items] == ["production_flow_range"] * 2


def test_a_date_is_written_without_the_time_when_it_is_midnight_utc() -> None:
    item = constraint(inputs.outcome()["report"], "brine_cooling_limit")

    assert item["message"].endswith("at 2027-04-24")


def test_a_tiny_number_is_written_in_full_precision_not_rounded_away() -> None:
    assert evaluate.amount({"value": 8.52695e-17, "unit": "-"}) == "8.52695 x 10^-17"
    assert evaluate.amount({"value": 1500000.0, "unit": "W/K"}) == "1500000 W/K"
    assert evaluate.amount({"value": 0.99999, "unit": "-"}) == "0.99999"


def test_a_missing_figure_says_why_without_the_code_prefix() -> None:
    item = constraint(inputs.outcome()["report"], "cooling_supply_temperature")

    assert item["message"] == (
        "missing: the plant has no unit of the role 'cooling_supply'; limit 20 degC"
    )


def test_a_figure_keeps_gemini_title_or_its_name() -> None:
    report = {"lcts": {"value": 1.0, "unit": "EUR/MWh", "title": "Cost of heat"}}
    report["lcoh"] = {"value": 2.0, "unit": "EUR/MWh"}

    kpis = evaluate.kpis_of(report)

    assert [kpi["title"] for kpi in kpis] == ["Cost of heat", "lcoh"]


def test_a_value_that_misses_the_limit_by_a_hair_is_not_rounded_onto_it() -> None:
    requirement = {
        "value": {"value": 0.1000004, "unit": "-"},
        "limit": {"value": 0.1, "unit": "-"},
    }

    assert evaluate.message_of(requirement) == "0.1000004 against the limit 0.1"
