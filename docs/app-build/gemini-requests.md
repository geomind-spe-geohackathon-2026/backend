# Requests to gemini

Everything the app needs from gemini, for the gemini thread to pick up. Items marked done were kept out; see `requests.md` for geomind and history.

## Schema

- Case-level `range`: accepted by the schema but read by nothing. Remove it, or define its meaning. `minimize` reads only plant ranges. The app hides the toggle on the case.
- Per-quantity allowed units for requirements: `unit` is a free string, so the form cannot offer a list.
- Role to quantities map for requirements: `on` and `quantity` are flat enums, so the form cannot filter quantities by role.
- Number bounds in the schema (`minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`), and a fraction or percent flag. The form shows and enforces them as soon as they exist; `boundsOf` in `frontend/src/shared/forms/json-schema.ts`.
- `kind` as a const on the case and economics schemas. The app sends `kind: <section name>`.
- Per-kind study schema: `objective` lists all 26 metrics, including `flow` and `temperature`, which are not objectives.
- Titles and descriptions on metrics and schema nodes: `gm.evaluate.metrics()` has name, quantity and unit only.

## Case

- `gm.case.missing`: a complete list of what a case still needs. Today a case with only `time` passes `from_dict`, and `check()` gives 0 issues; before `time` is set the list is `time` alone.
- `out_of_bounds` problems should carry the range as data. The message holds `{'min': 0.0} (SI)` and the backend rewords it by matching the text (`src/core/problems.py`).

## Plant

- `Plant.to_dict(structure=True)` keeps class-level parameters that `from_dict` refuses on a plant without a class: `params.depth` fails with "unknown parameter or control 'depth'". The backend drops the key, which also drops its search range.

## Studies

- `size` leaves coolers at the plant file's rating. On HeatingFullCoolingPlant the coolers stay at 40, 20 and 10 MW; peaks are 8.1, 3.6 and 9.4 MW (20%, 18%, 94% of rating).
- Please confirm: the compression cooler peak of 3.57 MW against a chiller peak of 3.34 MW implies a COP near 14.
- A way to mark what in `report.capacities` is a capacity and what is a size: pipes appear there with a length in m.
