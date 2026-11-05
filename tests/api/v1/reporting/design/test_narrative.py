from src.api.v1.reporting.design import figures, narrative


def day(geothermal: float, backup: float, electricity: float | None = None) -> dict:
    found = {
        "date": "2025-01-01",
        "source": "backup" if backup else "geothermal",
        "geothermal": {"value": geothermal, "unit": "MWh"},
        "backup": {"value": backup, "unit": "MWh"},
        "short": {"value": 0.0, "unit": "MWh"},
    }
    total = geothermal + backup + (electricity or 0.0)
    found["demand"] = {"value": total, "unit": "MWh"}
    if electricity is not None:
        found["electricity"] = {"value": electricity, "unit": "MWh"}
    return found


def test_the_heat_pumps_electricity_is_not_geothermal() -> None:
    coverage = {"heating": [day(60.0, 15.0, 25.0), day(60.0, 15.0, 25.0)]}

    assert narrative.share_text(coverage) == (
        "Of the heating demand, geothermal brine heat 60%, "
        "heat-pump electricity 25%, backup 15%."
    )
    tiles = dict(narrative.tiles_of({}, coverage))
    assert tiles["Geothermal share of heat"] == "60%"
    assert tiles["Heat-pump electricity share"] == "25%"
    chart = figures.supply_chart("Heating", coverage["heating"], ("Geothermal", "Backup"))
    assert figures.ELECTRICITY_WORD in chart


def test_a_coverage_stored_before_the_split_names_its_share_so() -> None:
    coverage = {"heating": [day(90.0, 10.0)]}

    assert narrative.share_text(coverage) == (
        "Geothermal, with any heat-pump electricity, covers 90% of the heating demand."
    )
    assert dict(narrative.tiles_of({}, coverage)) == {
        "Geothermal and heat-pump share": "90%"
    }
