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
    assert cold["reason"] == "the plant has no module at its edge that shows it"
    heat = next(k for k in parts["summary"]["kpis"] if k["name"] == "heat_delivered")
    assert heat["reason"] is None


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

    assert [kpi["title"] for kpi in kpis] == ["Cost of heat", "Cost of heat"]


def test_a_value_that_misses_the_limit_by_a_hair_is_not_rounded_onto_it() -> None:
    requirement = {
        "value": {"value": 0.1000004, "unit": "-"},
        "limit": {"value": 0.1, "unit": "-"},
    }

    assert evaluate.message_of(requirement) == "0.1000004 against the limit 0.1"


def rated(kind: str, value: float, unit: str) -> dict:
    return {
        "kind": kind,
        "capacity": {"value": value, "unit": unit},
        "peak": {"value": None, "unit": unit, "reason": "unused"},
        "share": {"value": None, "unit": "-", "reason": "unused"},
    }


RATINGS = {
    "capacities": {
        "d0": rated("production_pump", 300.0, "m3/h"),
        "supply_pipe": rated("pipe", 100.0, "m"),
        "heat_exchanger": rated("heat_exchanger", 1.5e6, "W/K"),
        "absorption_cooler": rated("cooler", 40.0, "MW"),
    }
}


def test_a_capacity_keeps_the_module_id_and_says_its_kind() -> None:
    first = evaluate.capacities_of(RATINGS)[0]

    assert (first["title"], first["kind"]) == ("d0", "Production pump")


def test_a_length_is_a_size_not_a_capacity() -> None:
    capacities = [item["name"] for item in evaluate.capacities_of(RATINGS)]
    sizes = [item["name"] for item in evaluate.sizes_of(RATINGS)]

    assert "supply_pipe" not in capacities
    assert sizes == ["supply_pipe"]


def test_a_large_conductance_has_a_readable_unit() -> None:
    exchanger = evaluate.capacities_of(RATINGS)[1]

    assert (exchanger["value"], exchanger["unit"]) == (1.5, "MW/K")


def test_a_cooler_says_its_rating_is_heat_rejected() -> None:
    assert evaluate.capacities_of(RATINGS)[2]["kind"] == "Cooler, heat rejected"


def requirement(**fields) -> dict:
    return {
        "name": "flow",
        "passed": True,
        "value": {"value": 300.0, "unit": "m3/h"},
        "limit": {"value": 300.0, "unit": "m3/h"},
        "unit_path": "d0",
        "quantity": "production_flow",
        "worst_step": "2027-01-27T00:00:00+00:00",
        **fields,
    }


def one(item: dict, limits: dict | None = None) -> dict:
    return evaluate.constraints_of({"requirements": [item]}, limits)[0]


def test_a_constraint_shows_both_bounds_margin_and_date() -> None:
    limits = {"flow": {"min": 50, "max": 300, "unit": "m3/h"}}

    found = one(requirement(), limits)

    assert found["title"] == "Flow"
    assert found["module"] == "d0"
    assert found["limit"] == "50 to 300 m3/h"
    assert (found["margin"], found["near"]) == (0, True)
    assert found["worst"] == "2027-01-27"


def test_a_lower_bound_has_its_direction() -> None:
    limits = {"count": {"min": 1}}
    figure = {"value": 2, "unit": "-"}
    item = requirement(name="count", quantity="count", value=figure, limit=figure)

    found = one(item, limits)

    assert found["limit"] == "≥ 1"
    assert found["unit"] == "-"


def test_a_share_of_one_reads_as_a_percentage_without_noise() -> None:
    figure = {"value": 0.7000000000001, "unit": "-"}
    item = requirement(
        name="eff", quantity="pump_efficiency", value=figure, limit=figure
    )

    found = one(item, {"eff": {"min": 0.7, "max": 0.7}})

    assert (found["value"], found["unit"]) == (70.0, "%")
    assert found["limit"] == "= 70 %"


def test_a_tornado_lists_the_largest_effect_first() -> None:
    def row(name: str, effect: float) -> dict:
        figure = {"value": 1.0, "unit": "K"}
        result = {"value": effect, "unit": "EUR/MWh"}
        return {
            "parameter": f"case.{name}",
            "metric": "lcts",
            "low": figure,
            "high": figure,
            "at_low": result,
            "at_high": result,
            "effect": result,
        }

    rows = evaluate.tornado_of({"found": {"rows": [row("a", 1), row("b", 3)]}})

    assert [item["parameter"] for item in rows] == ["b", "a"]
    assert rows[0]["metric"] == "Cost of thermal supply"


def test_a_spread_has_its_percentiles_and_draws() -> None:
    figure = {"value": 2.0, "unit": "kt"}
    summary = {"co2": {"mean": figure, "p5": figure, "p50": figure, "p95": figure}}

    rows = evaluate.spread_of({"found": {"summary": summary, "samples": [1, 2]}})

    assert rows[0]["draws"] == 2
    assert rows[0]["p95"] == 2.0


def test_other_runs_have_neither() -> None:
    assert evaluate.tornado_of({}) is None
    assert evaluate.spread_of({"found": {}}) is None


def test_a_result_says_what_it_is() -> None:
    assert evaluate.role_of({"found": {"rows": []}}) == "sensitivity"
    assert evaluate.role_of({"found": {"summary": {}}}) == "uncertainty"
    assert evaluate.role_of({}) == "design"


def test_a_design_states_its_doublets_and_depth() -> None:
    design = {
        "size": {"doublets": {"value": 2}},
        "params": {"depth": {"value": 2500, "unit": "m"}},
    }

    assert evaluate.design_facts(design) == {
        "doublets": 2,
        "depth": 2500,
        "depth_unit": "m",
    }
