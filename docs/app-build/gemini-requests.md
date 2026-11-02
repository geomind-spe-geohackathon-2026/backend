# Requests to gemini

Only what a UI feature needs that the public API cannot give, and real calculation or logic bugs. Refactor wishes stay out: the app uses the API as it is. Delivered in 0.5.3: unit lists, role quantities, bounds and fraction flag, `gm.case.missing`, per-kind study schema, metric titles.

## Bugs

- `Plant.to_dict(structure=True)` gives a document `from_dict` refuses: class-level `params.depth` fails with "unknown parameter or control 'depth'" on a plant without a class. The backend drops the key, which also drops its search range. Recheck on 0.5.3.
- `size` leaves coolers at the plant file's rating. On HeatingFullCoolingPlant the coolers stay at 40, 20 and 10 MW; peaks are 8.1, 3.6 and 9.4 MW (20%, 18%, 94% of rating).
- `on_progress` total is too low on a multi-doublet `minimize`: HeatingHeatPumpCoolingPlant with 20 evaluations reported `total` 60 but ran 240 trials. Recheck on 0.5.3.
- `daily_coverage` calls all cooling `geothermal`, also from an electric chiller. The app shows it as Plant; a neutral source name for cooling would be right.
- `gas_makeup` chemical and enthalpy flow in exceeds out by about 580 MWh of 21,643 on HeatingHeatPumpCoolingPlant, sized on the hackathon case. Please confirm that is expected.
