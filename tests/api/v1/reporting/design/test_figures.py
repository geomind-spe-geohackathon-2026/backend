from src.api.v1.reporting.design import figures, narrative


def day(source: str, demand: float) -> dict:
    return {
        "date": "2027-01-01",
        "source": source,
        "demand": {"value": demand, "unit": "MWh"},
        "geothermal": {"value": demand / 2, "unit": "MWh"},
        "backup": {"value": demand / 2, "unit": "MWh"},
        "short": {"value": 0, "unit": "MWh"},
    }


def test_the_key_figures_are_tiles() -> None:
    svg = figures.kpi_tiles([("LCTS", "40 EUR/MWh")])

    assert "LCTS" in svg
    assert svg.startswith("<svg")


def test_the_strip_has_a_cell_per_day() -> None:
    svg = figures.day_strips({"heating": [day("backup", 2), day("short", 2)]})

    assert svg.count(figures.SOURCE_COLORS["short"]) == 2


def test_the_supply_chart_names_its_peak() -> None:
    assert "peak 4 MWh" in figures.supply_chart(
        "Heat", [day("backup", 2), day("backup", 4)]
    )


def test_a_connected_module_stands_right_of_its_source() -> None:
    edges = [("a", "b"), ("b", "c"), ("c", "a")]

    rank = figures.ranks_of(["a", "b", "c"], edges[:2])

    assert (rank["a"], rank["b"], rank["c"]) == (0, 1, 2)
    assert set(figures.ranks_of(["a", "b", "c"], edges)) == {"a", "b", "c"}


def test_capital_cost_groups_by_kind_with_its_unit_cost() -> None:
    report = {
        "capex": {
            "modules": {
                "a": {"value": 2.0, "kind": "drilling"},
                "b": {"value": 3.0, "kind": "drilling"},
            }
        }
    }
    economics = {
        "file": "e.json",
        "capex": {"drilling": {"value": 100, "unit": "EUR/m"}},
    }

    assert narrative.capex_rows(report, economics) == [
        ["Drilling", "5 MEUR", "100 EUR/m", "e.json, capex.drilling"]
    ]
