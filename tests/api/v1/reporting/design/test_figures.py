from src.api.v1.reporting.design import figures, narrative, schemas, services


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


def test_the_supply_chart_has_an_axis_and_a_legend() -> None:
    days = [day("backup", 24), day("backup", 48)]

    svg = figures.supply_chart("Heat", days, ("Geothermal", "Backup"))

    assert "MW, daily mean" in svg
    assert ">Demand<" in svg


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


def test_a_module_id_reads_in_words() -> None:
    assert narrative.module_words("peak_boiler") == "Peak boiler"
    assert narrative.module_words("d0") == "d0"


def test_cooling_supply_is_not_called_geothermal() -> None:
    assert figures.source_word("cooling", "geothermal") == "Plant"
    assert figures.source_word("heating", "geothermal") == "Geothermal"


def test_a_flowsheet_goes_under_the_plant_section_of_an_export() -> None:
    section = schemas.ReportSection(key="design", title="Plant", markdown="Text")
    report = schemas.Report(title="T", sections=[section], flowsheet={})

    shown = services.with_flowsheet(report, "<svg></svg>")

    assert "![Flowsheet](data:image/svg+xml" in shown.sections[0].markdown
    assert services.with_flowsheet(report, "<script>") == report


def test_a_flowsheet_page_follows_the_capacities_when_they_are_chosen() -> None:
    plant = schemas.ReportSection(key="design", title="Plant", markdown="Text")
    rated = schemas.ReportSection(key="capacities", title="Capacities", markdown="Text")
    report = schemas.Report(title="T", sections=[plant, rated], flowsheet={})

    shown = services.with_flowsheet(report, "<svg></svg>")

    assert "Flowsheet" not in shown.sections[0].markdown
    assert "Flowsheet" in shown.sections[1].markdown


def test_noise_on_a_bound_is_no_margin() -> None:
    assert narrative.margin_text(1e-5, "-") == "0"
