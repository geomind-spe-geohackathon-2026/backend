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
