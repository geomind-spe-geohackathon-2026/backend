from types import SimpleNamespace

from src.api.v1.reporting.design import document, figures, narrative, schemas, services
from tests import design_inputs


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
        ["Drilling", "5\u2009MEUR", "100\u2009EUR/m", "e.json, capex.drilling"]
    ]


def test_a_module_id_reads_in_words() -> None:
    assert narrative.module_words("peak_boiler") == "Peak boiler"
    assert narrative.module_words("d0") == "d0"


def test_cooling_supply_is_not_called_geothermal() -> None:
    assert figures.source_word("cooling", "geothermal") == "Plant"
    assert figures.source_word("heating", "geothermal") == "Geothermal"


def test_a_flowsheet_goes_where_the_plant_section_marks_it() -> None:
    marked = f"Lead\n\n{document.FLOWSHEET_MARKER}\n\n*Figure 3.1 - Flowsheet*"
    section = schemas.ReportSection(key="design", title="Plant", markdown=marked)
    report = schemas.Report(title="T", sections=[section], flowsheet={})

    shown = services.with_flowsheet(report, "<svg></svg>").sections[0].markdown
    dropped = services.with_flowsheet(report, "<script>").sections[0].markdown

    assert shown.index("Lead") < shown.index("![Flowsheet](data:image/svg+xml")
    assert shown.index("![Flowsheet]") < shown.index("*Figure 3.1")
    assert document.FLOWSHEET_MARKER not in dropped
    assert "![Flowsheet]" not in dropped


def test_noise_on_a_bound_is_no_margin() -> None:
    assert narrative.margin_text(1e-5, "-") == "0"


def test_the_plant_section_names_the_study_kind_and_its_unit_groups() -> None:
    outcome = design_inputs.outcome()
    result = SimpleNamespace(
        name="Best",
        content={**outcome, "coverage": None},
        summary={"checks": {}},
        case_version=1,
        plant_version=None,
    )
    study = SimpleNamespace(kind="minimize", settings={}, name="best")
    inputs = document.Inputs(result, study, None, None, {}, {})

    text = document.design_section(inputs, document.Numbers(3))

    assert "Find the best design" in text
    assert "Heating plant" in text
    for heading in ("### 3.1 Subsurface", "### 3.3 Heating", "### 3.5 Grids"):
        assert heading in text
    assert "*Table 3.1 - Subsurface units" in text
    assert "| ---: |" in text


def test_the_full_flowsheet_goes_in_the_appendix_of_an_export() -> None:
    plant = schemas.ReportSection(key="design", title="Plant", markdown="Text")
    extra = schemas.ReportSection(key="appendix", title="Appendix", markdown="Text")
    report = schemas.Report(title="T", sections=[plant, extra], flowsheet={})

    shown = services.with_full_flowsheet(report, "<svg></svg>")

    assert "Detailed flowsheet" not in shown.sections[0].markdown
    assert "![Detailed flowsheet](data:image/svg+xml" in shown.sections[1].markdown


def test_no_appendix_means_no_full_flowsheet() -> None:
    plant = schemas.ReportSection(key="design", title="Plant", markdown="Text")
    report = schemas.Report(title="T", sections=[plant], flowsheet={})

    assert services.with_full_flowsheet(report, "<svg></svg>") == report
