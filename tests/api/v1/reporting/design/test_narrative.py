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
        "Of the heating demand, geothermal brine heat 60\u2009%, "
        "heat-pump electricity 25\u2009%, backup 15\u2009%."
    )
    tiles = dict(narrative.tiles_of({}, coverage))
    assert tiles["Geothermal share of heat"] == "60\u2009%"
    assert tiles["Heat-pump electricity share"] == "25\u2009%"
    chart = figures.supply_chart(
        "Heating", coverage["heating"], ("Geothermal", "Backup")
    )
    assert figures.ELECTRICITY_WORD in chart


def test_a_coverage_stored_before_the_split_names_its_share_so() -> None:
    coverage = {"heating": [day(90.0, 10.0)]}

    assert narrative.share_text(coverage) == (
        "Geothermal, with any heat-pump electricity, covers 90\u2009% of the heating "
        "demand."
    )
    assert dict(narrative.tiles_of({}, coverage)) == {
        "Geothermal and heat-pump share": "90\u2009%"
    }


def cooling_day(source: str, demand: float, other: float) -> dict:
    found = day(demand - other, other)
    found["source"] = source
    found["no_demand"] = demand == 0
    found["labels"] = {"main": "Plant", "other": "Electric chiller"}
    return found


def test_cooling_days_use_geminis_labels_and_count_no_demand_apart() -> None:
    from src.api.v1.reporting.design import document

    days = [cooling_day("geothermal", 0, 0), cooling_day("backup", 10, 10)]

    text = document.days_reading([("cooling", days)])
    rows = document.performance_rows([("cooling", days)])

    assert "1 had a demand and 1 had none" in text
    assert "1 also needed Electric chiller" in text
    assert "backup" not in text.lower()
    assert rows == [["Cooling", "Plant", "0", "Electric chiller", "1", "0", "1"]]


def test_the_fuel_burned_shows_the_produced_gas() -> None:
    from src.api.v1.reporting.design import document

    report = {
        "gas_bought": {"value": 34_060.0, "unit": "MWh"},
        "co2": {"fuel_energy": {"value": 49_000.0, "unit": "MWh"}},
        "cop": {"value": 18.86, "unit": "-"},
        "heat_pump_cop": {"value": 3.9, "unit": "-"},
    }

    rows = dict(document.fuel_rows(report) + document.ratio_rows(report))

    assert rows["Fuel burned on site"] == "49 GWh"
    assert rows["Produced gas burned (fuel burned less gas bought)"] == "14.94 GWh"
    assert "Heat pump COP" in rows or any("COP" in key for key in rows)
    assert len(rows) == 4
