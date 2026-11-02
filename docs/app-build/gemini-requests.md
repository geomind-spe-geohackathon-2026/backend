# Requests to gemini

Only what a UI feature needs that the public API cannot give, and real calculation or logic bugs. Refactor wishes stay out: the app uses the API as it is.

## New UI needs

- Per-quantity allowed units for requirements: `unit` is a free string, so the form cannot offer a list.
- Role to quantities map for requirements: `on` and `quantity` are flat enums, so the form cannot filter quantities by role.
- Number bounds in the schema (`minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`), and a fraction or percent flag. The form shows and enforces them as soon as they exist.
- `gm.case.missing`: a complete list of what a case still needs. Today a case with only `time` passes `from_dict`, `Case.check()` gives 0 issues, and `gm.check(plant, case)` stops at the first missing value (`site.fluid.density`).
- Per-kind study schema: `objective` lists all 26 metrics, including `flow` and `temperature`, which are not objectives.
- Titles on metrics: `gm.evaluate.metrics()` has name, quantity and unit only.

## Bugs

- `Plant.to_dict(structure=True)` gives a document `from_dict` refuses: class-level `params.depth` fails with "unknown parameter or control 'depth'" on a plant without a class. The backend drops the key, which also drops its search range.
- `size` leaves coolers at the plant file's rating. On HeatingFullCoolingPlant the coolers stay at 40, 20 and 10 MW; peaks are 8.1, 3.6 and 9.4 MW (20%, 18%, 94% of rating).
- Please confirm: the compression cooler peak of 3.57 MW against a chiller peak of 3.34 MW implies a COP near 14.
