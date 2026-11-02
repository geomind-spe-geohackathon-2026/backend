# gemini 0.5.0 public API inventory for the backend (section 5.3)

Read-only. Verified against the snapshot `backend/.tmp/snap/gemini-0.5.0` (its `gemini/` package is byte-identical to the installed venv package, `backend/.venv/lib/python3.12/site-packages/gemini`, version `0.5.0`, Python 3.12.10). Every signature below was read with `inspect.signature` on the installed package; every output sample was produced by running it on `examples/hackathon_2026` (case.json, plants/HeatingPlant.json and siblings). Probe scripts live in the scratch folder `/private/tmp/claude-501/-Users-sahand-Desktop-geomind-spe-geohackathon-2026-gemini/ae9e78ce-1434-5943-b63e-55d2903b9e35/scratchpad/inv/`. Nothing in `../gemini`, `../gemini-forward` or `../gemini-forward-tmp` was touched.

Docs read: `snap/gemini-0.5.0/.claude/docs/api.md` (the public API page; its header still says `gm.__version__ = "0.3.0"`, which is stale, the package is 0.5.0), `plants.md`, `CHANGELOG.md` (0.5.0 section). `gm.__all__` has 35 names.

Status key: **present** = public name, works as described. **partial** = public pieces exist, the need is met only with backend glue or a caveat. **MISSING** = no public way in 0.5.0.

## Summary table

| # | Need (section 5.3) | Status | gemini name and signature |
|---|---|---|---|
| 1 | Case from/to dict | present | `gm.Case.from_dict(data, files=None, folder=None)`, `case.to_dict()` |
| 2 | Case JSON schema with units | present | `gm.Case.schema()` (no argument) |
| 3 | Case validate: missing + problems | partial | `gm.Case.from_dict` raises one `ValidationError` whose `.problems` lists all of them; see "missing vs structural" |
| 4 | Read the files a case names, from bytes | present | `gm.Case.from_dict(data, files={name: bytes})`, `case.files()` returns `{name: bytes}` |
| 5 | Case series as `[time, value]` points | partial, points MISSING | `case.leaf(path).series` (no points method) |
| 6 | Case schema section titles | MISSING | none in the schema (no `title`/`description` below the root) |
| 7 | Plant from dict/json, to dict | present | `gm.Plant.from_dict(data)`, `gm.Plant.from_json(path)`, `plant.to_dict(structure=False)`, `plant.to_json(path, structure=False)` |
| 8 | Plant validate: problems with paths, no build | partial | `gm.Plant.from_dict` raises all problems (builds in memory, runs nothing); `plant.check()` on a built plant lists missing values |
| 9 | Plant validate / from_spec / migrate | MISSING | `gm.plants.validate`, `gm.plants.from_spec`, `gm.plants.migrate` are absent; `Plant.from_spec`, `Plant.to_spec` absent |
| 10 | Plant named templates with title/description/purpose | partial | `gm.plants.names(category=None)`, `gm.plants.get(name)`, `plant.purpose`, `plant.describe()["type"]`, `plant.describe()["summary"]` |
| 11 | Module registry (type, title, category, summary, parameter schema with units) | present, title MISSING as a field | `gm.modules.names(category=None)`, `gm.modules.categories()`, `gm.modules.get(name)`, `Module.describe()`, `Module.parameter_schema()` |
| 12 | Module title | MISSING as a field | closest: `describe()["type"]` (class name) and `parameter_schema()["title"]` (class name) |
| 13 | Port stream type | present | `module.describe()["inlets"|"outlets"][port]["kind"]`, fields `{m_dot, T, p}` with `unit` |
| 14 | Study kinds with settings schemas | partial | `gm.Study.schema()["properties"]["method"]["enum"]` = run, minimize, sample, sensitivity; no per-kind settings schema |
| 15 | Study run with progress callback and cancel check | MISSING for studies | `gm.Study.run(plants=None)` and `gm.study.*` take no callback; progress and cancel exist only for `gm.simulate` (`Callback.on_progress`) |
| 16 | Study result object | present | `gm.Study.run()` returns `gm.study.StudyResult` (`runs`, `comparison`, `best`, `cases`, `study`, `to_dict`, `to_json`) |
| 17 | Evaluate KPIs with units | present | `gm.evaluate.report(plant, case, results)`, `gm.evaluate.totals(plant, case, results)`, `Value.to(unit)` |
| 18 | Capacities | present | `gm.evaluate.capacities(plant, case, results)` |
| 19 | Daily coverage by source | MISSING | no daily or per-source coverage output; `totals` gives one `heating_coverage` ratio |
| 20 | Constraint checks pass/fail/not assessed | present | `gm.evaluate.requirements(plant, case, results)`, `report["requirements"]`, `gm.evaluate.verdict(...)` |
| 21 | Compare with Pareto | present | `gm.evaluate.compare(reports, by)`, `Comparison.to_frame()` |
| 22 | Units | present | `gm.units.Unit`, `gm.units.Quantity(value, unit)`, `gm.units.convert(value, from_unit, to_unit, quantity=None)`, `gm.units.names(quantity=None)`, `gm.units.fits(unit, quantity)` |
| 23 | Errors | present, mapping is backend work | `gm.errors.ValidationError`, `DefinitionError`, `PhysicsError`, `RunError`, `Cancelled`, `NotImplementedYet`, `GeminiError`; `.code`, `.path`, `.problems`, `.suggestions` |
| 24 | Simulate with progress and cancel | present | `gm.simulate(plant, case=None, plan=None, clock=None, checkpoint=None, checkpoint_every=None, backend='numpy', callbacks=None, on_error='raise', compile=True)` |

## 1. Case

**Signatures (live):**
- `gm.Case.from_dict(data, files=None, folder=None)`, `gm.Case.from_json(path)`
- `case.to_dict()`, `case.to_json(path)`, `case.files()`, `gm.Case.schema()`
- `case.check()`, `case.leaf(path)`, `case.field(path)`, `case.with_value(path, number)`

**Real output, `case.to_dict()` keys:** `['format', 'kind', 'name', 'time', 'site', 'demand', 'utilities', 'economics', 'requirements']`.

**Real output, `case.files()`:** `{'data/demand.csv': b'time,heating_demand_MWth,cooling_demand_MWcool\n2027-01-01T00:00:00+00:00,24.313,0.0\n...', 'economics.json': b'{...'}` (bytes, sizes 13776 and 3762 for the example).

**Schema units:** units are an enum on each leaf, not a separate map. Example from `Case.schema()`: demand power `unit: {"enum": ["GW", "MW", "W", "kW"]}`; ground temperature `unit: {"enum": ["C", "K", "degC", "°C"]}`. Each leaf also carries `range` and `uncertainty` objects.

**Case schema section titles: MISSING.** The schema has `title: "Case"` at the root and no `title` or `description` below it. Top-level properties are `format, kind, name, about, site, demand, utilities, time, initial_state, economics, requirements`. The section labels must be a fixed table in the backend.

### Missing vs structural split (case)

`Case.check()` returns `[]` on any built case, because a case that does not load cannot be built. The working split is on the error raised by `from_dict`, which carries every problem.

Real probe, one document with three problems (a missing demand, a wrong unit, a non-numeric value):

```
n problems 3
   invalid_value site.ground.surface_temperature.value | ... expected a number in degC (temperature)
   invalid_unit site.ground.gradient.unit | ... unit = 'm3/h'; expected a unit of temperature gradient: K/km, K/m
   missing_value demand.heating.power | demand.heating.power: power is missing
```

Rule for the backend: `code == "missing_value"` is missing; every other code is structural (`invalid_value`, `invalid_unit`, `unknown_name`, `out_of_bounds`, `old_format`). Internally the kind `missing` maps to `missing_value` and all other kinds map to structural codes (`gemini/errors/base.py`, `ISSUE_KINDS`).

A missing value that the case does not require (`site.ground.gradient` removed) is not an issue at all: `from_dict` succeeds and `check()` is `[]`.

### Series

`case.leaf(path)` returns a `Leaf` with `value`, `unit`, `quantity`, `range`, `range_si`, `uncertainty`, `uncertainty_si`, `si`, `series`, `to_json`.

`leaf.series` (in the example, `demand.heating.power`) is a `Series` dataclass with fields `file, column, unit, time, values, quantity`, a property `si`, and methods `to_csv`, `to_json`.

- `series.time`: a UTC `DatetimeIndex` (365 entries for the example, 2027-01-01 to 2027-12-31).
- `series.values`: numbers in the file's unit (`unit == "MW"`, `values[:3] == [24.313, 22.984, 23.218]`).
- `series.si` (a property): the same numbers in SI (`[24313000., 22984000., 23218000., ...]`).
- `series.to_json()`: only the reference `{'file': 'data/demand.csv', 'column': 'heating_demand_MWth', 'unit': 'MW'}`, no numbers.

**Points as `[time, value]`: MISSING.** No public method returns points. The backend builds them from `time` and `si` (pure data conversion, no physics):

```python
pts = [[t.isoformat(), float(v)] for t, v in zip(s.time, s.si)]
# [['2027-01-01T00:00:00+00:00', 24313000.0], ['2027-01-02T00:00:00+00:00', 22984000.0], ...]
```

**Read from stored bytes: present.** `gm.Case.from_dict(data, files={name: bytes})` reads the CSV without touching disk (verified: 365 points read from bytes). Without `files` it raises `missing_value` naming each missing file.

## 2. Plant

### What the plant document looks like

The file has a header `{"format": 1, "kind": "plant", "name": "<name>"}`, plus `type` (the class name, optional for a plant without a class), `size` (structural count such as `{"doublets": {"value": 2, "range": {"min": 1, "max": 3}}}`), `params` (a tree of leaves, each `{"value", "unit", "range"?}` and `history` for dated entries), and for a plant built from modules, `modules` and `connections`. Other optional keys in `docs/schemas/plant.schema.json`: `fluids`, `inlets`, `outlets`, `outputs`, `boundary`, `constraints`, `about`.

`format` must be `1`. `format: 2` raises `old_format` with path `format`.

Real example, first lines of `examples/hackathon_2026/plants/HeatingPlant.json` (keys `['format', 'kind', 'name', 'type', 'size', 'params']` as written by `to_dict`):

```json
{"format": 1, "kind": "plant", "name": "HeatingPlant", "type": "HeatingPlant",
 "size": {"doublets": {"value": 2}},
 "params": {"depth": {"value": 2500, "unit": "m", "range": {"min": 2000.0, "max": 3500.0}},
            "backup": {"value": "peak"}, ...}}
```

Other example plant files: `examples/hackathon_2026/plants/` (HackathonPlant, HeatingAbsorptionCoolingPlant, HeatingCoolingPlant, HeatingFullCoolingPlant, HeatingHeatPumpCoolingPlant, HeatingPlant) and `examples/shallow_district/plants/HeatingHeatPumpCoolingPlant.json`. The schema is `gm.plants.schema()` (`required: ['format', 'kind', 'name']`) and `docs/schemas/plant.schema.json`.

### Can a document be checked without building?

**Partial.** There is no public pure-document validator. `gm.Plant.from_dict(data)` builds the plant in memory (no run) and raises one `ValidationError` carrying every structural problem. Probe, one document with three problems:

```
n problems 3 ['unknown_name', 'invalid_unit', 'invalid_value']
{"path": "params.depth.unit", "code": "invalid_unit", "message": "params.depth.unit: unit = 'm3/h'; expected a unit of length: ft, in, km, m, mm", "suggestions": []}
```

Other codes observed: `unknown_name` (an unknown key, path `params.zz_unknown`), `invalid_value` for a value outside an enum (`params.backup.value`, suggestions `('none',)`), `out_of_bounds` (`params.depth` value -5 m), `old_format` (`format`).

A missing value does not raise in `from_dict`. It is found by `plant.check()` on the built plant, one `Issue` per unset parameter:

```
Issue(kind='missing', path='params.d0.gradient', ...)
problem(): {"path": "params.d0.gradient", "code": "missing_value",
            "message": "d0.gradient: no value [K/m]: Increase of undisturbed rock temperature with depth; empty takes it from the case",
            "suggestions": []}
```

`Issue` fields: `path, kind, message, quantity, accepted, suggestions, code, problem`. `check()` returns the file's structural issues plus the `missing` ones. The `Issue` class is not exported from `gm`, but its instances and `problem()` are returned by the public calls.

The JSON Schema (`gm.plants.schema()`) can check shape without building, but the `jsonschema` package is not installed in the backend venv, so using it means adding a dependency.

**Backend call to use:** `gm.Plant.from_dict` in a try block, reading `e.problems`. Building in memory is the only public route, and it runs nothing.

### Named templates: title, description, purpose

`gm.plants.names()` returns 16 plant classes. The five template plants (`.claude/docs/plants.md`) are `HeatingPlant`, `HeatingCoolingPlant`, `HeatingFullCoolingPlant`, `HeatingAbsorptionCoolingPlant`, `HeatingHeatPumpCoolingPlant`. `DistrictNetwork` and `MultiWellPlant` also take a size.

Real output, `gm.plants.names("heating")` = `['HeatingPlant']`, `gm.plants.names("both")` = `['DistrictNetwork', 'HeatingAbsorptionCoolingPlant', 'HeatingCoolingPlant', 'HeatingFullCoolingPlant', 'HeatingHeatPumpCoolingPlant', 'MultiWellPlant']`, `gm.plants.names("cooling")` = `[]`.

| Field | Public source | Value |
|---|---|---|
| title | `plant.describe()["type"]` | class name, e.g. `HeatingPlant`. No human title exists: **title MISSING**, the backend keeps its own label table |
| description | `plant.describe()["summary"]` (same text as `["doc"]`) | e.g. `Geothermal heating: doublet, heat exchanger, peak boiler and the heating consumer.` |
| purpose | `plant.purpose` (class attribute) | `heating` (HeatingPlant); `both` (HeatingCoolingPlant, HeatingFullCoolingPlant, HeatingAbsorptionCoolingPlant, HeatingHeatPumpCoolingPlant, DistrictNetwork, MultiWellPlant); `None` for the other 9 classes |

`gm.plants.get(name)` returns a new plant without values. `gm.plants.capabilities()` gives, per class, `{roles, schedulable, ranges}`, e.g. `HeatingPlant: {'roles': ['boiler', 'doublet', 'heat_exchanger', 'heating_supply', 'plant'], 'schedulable': True, 'ranges': ['size.doublets', 'params.depth']}`.

No class has purpose `cooling`, so `gm.plants.names("cooling")` is empty.

### Plant migration: MISSING

`gm.plants.migrate`, `gm.plants.validate`, `gm.plants.from_spec`, `gm.plants.from_template`, `gm.plants.templates`, `gm.plants.example`, `Plant.from_spec`, `Plant.to_spec`, `Plant.validate`, `Plant.missing_parameters`, `Module.missing_parameters` are all absent (verified). `gm.profiles`, `gm.checks`, `gm.challenge_rules`, `gm.units.parse` are absent too. The CHANGELOG and `api.md` list them as removed.

Closest public way: an old-format file raises `old_format` from `from_dict`; the backend should report it (`plant_invalid`). Converting an old file to format 1 is not possible through gemini, so **none exists**.

## 3. Modules

- `gm.modules.categories()` = `['subsurface', 'wells', 'pumps', 'treatment', 'exchangers', 'heating', 'cooling', 'power', 'storage', 'piping', 'grids', 'environment', 'control', 'plants']`
- `gm.modules.names()` = 64 names (48 equipment + 16 plants). `gm.modules.names("pumps")` = `['CentrifugalPump', 'CirculationPump', 'ESP', 'GasCompressor', 'InjectionPump', 'LineShaftPump']`.
- `gm.modules.get("ESP")` returns the class; instantiate it for `describe()`.

Real `describe()` output for `gm.modules.get("ESP")()` (abridged):

```
name='esp', type='ESP', category='pumps',
summary='Electrical submersible pump installed inside a production well.',
doc='Electrical submersible pump installed inside a production well.',
inlets: {"fluid_in": {"kind": "brine", "fields": {"m_dot": {"unit": "kg/s"}, "T": {"unit": "K"}, "p": {"unit": "Pa"}}},
         "power_in": {"kind": "electricity", "fields": {"power": {"unit": "W"}}}}
outlets: {"fluid_out": {"kind": "brine", "fields": {...}}}
```

Keys of `describe()`: `name, type, category, summary, doc, parameters, controls, boundaries, measured, state, inlets, outlets, outputs, children, connections, values`.

`parameters` items carry `type, unit, quantity, default, minimum, maximum, enum, description, section`, e.g. `stage_count: {"type": "integer", "unit": "-", "quantity": "count", "minimum": 0, ...}`.

**Module title: MISSING as a field.** Closest: `describe()["type"]` (class name) and `describe()["summary"]`. `parameter_schema()` has `title: "ESP"`, the class name, `description` absent. Parameter schema units are on each property as `unit` and `quantity`.

**Port stream type: present.** `describe()["inlets"][port]["kind"]` and `["outlets"][port]["kind"]`. Stream kinds from `gemini.streams.kinds.names()`: `brine, hot_water, chilled_water, gas, electricity, fuel, heat, air, waste, chemical`. `None` means the port takes any stream. Public `gm.streams` exports `Stream, Fluid, Ports, BRINE, WATER, GLYCOL_30, STEAM`.

## 4. Study

- `gm.Study.from_dict(data, files=None, folder=None)`, `gm.Study.from_json(path)`, `study.to_dict()`, `study.to_json(path)`, `study.check()`, `study.run(plants=None)`, `gm.Study.schema()`.
- `gm.study.size(plant, case)`, `gm.study.minimize(plant, case, objective, evaluations, seed, *, plan=None)`, `gm.study.sample(plant, case, metrics, samples, seed, *, plan=None)`, `gm.study.sensitivity(plant, case, metrics, *, plan=None)`, `gm.study.calibrate(...)`.

**Kinds (method enum), present:** `gm.Study.schema()["properties"]["method"] == {"enum": ["run", "minimize", "sample", "sensitivity"]}`. `prepare` is an array of enum `["size"]`. Flat properties: `format, kind, name, about, cases, plants, prepare, method, objective, metrics, evaluations, samples, seed`. `required: ['format', 'kind', 'name', 'cases', 'plants', 'method']`.

**Settings schema per kind: MISSING.** The schema is flat. The per-method required keys (`REQUIRED = {"minimize": ("objective", "evaluations", "seed"), "sample": ("metrics", "samples", "seed"), "sensitivity": ("metrics",), "run": ()}`) are private in `gemini/study/study.py`. The public way to learn them is `study.check()`, which returns `missing` issues for the keys a method needs.

Real results:
- `Study.from_json(".../study_sensitivity.json").check()` = `[]`; `.run()` took 4.5 s and returned `StudyResult` with `runs` (list of `Run`), `comparison` (dict), `best`, `cases`, `study`, `to_dict`, `to_json`.
- `gm.study.size(plant, case)` returns a `gm.Plant` with `sizing = {"sized": [{path, value, reason}], "unchanged": [...], "broken": [...], "simulation": str}`. Sample `sized` entry: `{'path': 'size.doublets', 'value': Quantity(value=3, ...), 'reason': '3 doublet(s) of 14.48 MW each at the flow limit 300 m3/h ...'}`.
- `gm.study.sensitivity(plant, case, ["lcts"])` returns a `Tornado` (6 rows). `to_frame()` columns `parameter, metric, low, high, value_unit, at_low, at_high, effect, unit`.
- `gm.study.sample(plant, case, ["lcts"], 3, 0)` returns a dict `{samples, summary}`; `summary["lcts"]` is `{mean, p5, p50, p95, failed}` of `Value`s.
- `gm.study.minimize(plant, case, "lcts", 10, 0)` returns `{best, feasible, history, evaluations}`. `best` is a `Best` (a `Value`), with `best.parts["parameters"]` = `{name: Quantity}` and `best["plant"]` = the best `gm.Plant`. `history` is a list of `Value`s. `evaluations` counts per doublet count (10 requested, 60 reported, 3 doublet counts). `evaluations` below 10 for two variables raises `ValidationError` ("2 variables need at least 10").

**Progress callback and cancel check for studies: MISSING.** No study function, nor `Study.run`, accepts a callback. No progress event exists. The only public cancel is the engine's callback, which applies to `gm.simulate` only (section 6).

Closest public way: run each study in a worker process and terminate that process to cancel, with status "running" only. Per-trial progress does not exist in 0.5.0, so **none exists**.

## 5. Evaluate

Every function takes `(plant, case, results)`, except `capex` and `size`.

- `gm.evaluate.report(plant, case, results)` returns a `Report` (a dict). Keys: `heat_delivered, cold_delivered, boiler_heat, electricity_bought, gas_bought, capacities, capex, opex, lcts, lcoh, lcoc, co2, requirements, passed, verdict, failed_steps, failures, services`. Each cost is a `Value`; `report["lcts"].to("EUR/MWh")` = `47.81` for HeatingPlant on the example.
- `gm.evaluate.totals(plant, case, results)` keys: `heat_delivered, heat_useful, heat_surplus, cold_delivered, cold_useful, cold_surplus, electricity_bought, electricity_sold, gas_bought, co2_emitted, methane_emitted, waste, chemicals, losses, heating_coverage, cooling_coverage, cop, peak_heat, peak_cold`.
- `gm.evaluate.capacities(plant, case, results)` returns `{path: {kind, capacity, peak, share}}`, values as `Value`; sample `('d0', {'kind': 'production_pump', 'capacity': Value(value=0.0833, unit=m3/s), ...})`.
- `gm.evaluate.requirements(plant, case, results)` returns a list of `{name, role, unit_path, quantity, passed, value, limit, worst_step}`. `passed` is `True`, `False`, or `None` with reason `no_value`. Sample: `{'name': 'production_flow_range', 'passed': True, 'role': 'doublet', 'unit_path': 'd0', ...}`.
- `gm.evaluate.verdict(plant, case, results)` returns `{feasible, reasons}`. Sample on HeatingPlant: `{'feasible': False, 'reasons': [{'kind': 'requirement', 'name': 'cold_delivered', 'message': 'the run gives no cold_delivered for the cooling'}]}`.

**Daily coverage by source: MISSING.** `totals` gives one ratio per run (`heating_coverage`), not per day and not per source. Closest: `results.get(path, field, units=...)` returns `{time, value, unit}` per step. Sources of heat for the consumer are readable per step: `peak_boiler.fluid_out.enthalpy_flow`, `heat_exchanger.duty`, `heating_consumer.unmet_demand`. The backend sums these per calendar day; that is arithmetic over results, not physics. For a daily run (example: 365 steps) each step is one day. For hourly runs the backend must group by day itself.

**Compare with Pareto: present.** `gm.evaluate.compare(reports, by)`: `by` is a name, a list of names, or `{metric: "min"|"max"}`. Returns `Comparison`, a list of entries `{index, values, ranks, pareto, feasible}` (plus `reasons` for an infeasible one). Probe over three example plants (lcts, co2):

```
pareto:   [False, False, True]
feasible: [False, True, True]
to_frame columns: ['lcts [EUR/MWh]', 'co2 [kt]', 'rank_lcts', 'rank_co2', 'pareto', 'feasible']
```

## 6. Simulate, callbacks, errors

- `gm.simulate(plant, case=None, plan=None, clock=None, checkpoint=None, checkpoint_every=None, backend='numpy', callbacks=None, on_error='raise', compile=True)` returns `Results`. Real run: 0.33 s for HeatingPlant on the example.
- `Results` public: `names()`, `get(path, field, start=None, end=None, units=None)`, `summary(...)`, `errors()`, `to_frame(units=None, table='series')`, `to_dict(units=None)`, `energy_report(units=None)`, `to_npz`, `from_npz`, `to_bytes`, `from_bytes`, `end_state`. `get` returns `{time, value, unit}`.

**Progress callback: present on `gm.simulate` only.** The hook is `on_progress(self, engine, done, total)`. Cancel: raise `gm.errors.Cancelled` from it. Probe: cancel at `done >= 200` of 365 ticks, raised `Cancelled` (`code == "cancelled"`) after 0.55 s.

`gm.Callback` is not exported (nor `gm.engine.Callback`). The base class is only at `gemini.engine.callbacks.Callback`, an internal path. A callback object works if it defines all six hook methods (`on_run_start, on_step_start, on_step_end, on_progress, on_error, on_run_end`) and `changes_run = False`. A duck-typed object missing `on_error` fails with `AttributeError`. Verified: all six defined, `Cancelled` raised at tick 100 of 365, checkpoint written.

**Observation, not resolved:** `gm.resume(checkpoint)` after that cancel raised `ValidationError` (missing_value): "uninitialized parameters: d0.gradient ... empty takes it from the case". `gm.resume` after an uncancelled checkpointed run (365 steps) returned 365 steps. So resume after a cancel may fail in 0.5.0. Not investigated further; worth a check before the app relies on cancel-then-resume.

**Errors: present.** `gm.errors.__all__` = `CODES, ROW_CODES, GeminiError, GeminiWarning, ValidationError, DefinitionError, PhysicsError, RunError, Cancelled, NotImplementedYet`. `CODES` (37 values) includes `missing_value, invalid_value, invalid_unit, unknown_name, out_of_bounds, old_format, invalid_format, invalid_connection, invalid_design, cancelled, step, checkpoint, ...`. `ROW_CODES`: `missing_value, invalid_inlet, out_of_bounds, out_of_range, no_convergence, module_error`.

Backend mapping: gemini has no `case_invalid`, `plant_invalid` or `missing_inputs` code. Map by the call that raised (`Case.from_dict` vs `Plant.from_dict` vs `simulate`) and by `code == "missing_value"` (to `missing_inputs`). `inputs_missing` is listed in `CODES` but raised by nothing in 0.5.0 (its raisers, `gm.profiles.get` and `gm.plants.example`, were removed).

## 7. Units

`gm.units`: `Unit` (str enum, 115 members, e.g. `Unit.M3_PER_H == "m3/h"`), `Quantity(value, unit)` with `.value, .unit, .si, .to(unit, quantity=None), .to_dict()`, `Quantity.from_dict(d)`, `convert(value, from_unit, to_unit, quantity=None)`, `names(quantity=None)` (`names("power")` = `['GW', 'MW', 'W', 'kW']`), `fits(unit, quantity)`, and the `display` submodule (its `DISPLAY_UNITS` table is in `gemini.units.display`). Sample: `gm.units.convert(1, "bar", "Pa")` = `100000.0`; `Quantity(150, "m3/h").to("m3/s")` = `0.041666...`.

A text value such as `"150 m3/h"` is refused. A bare number with a dimension is refused at every public door (`invalid_value`, `Case.from_dict` example: `site.ground.gradient: 30 has no unit`).

## Corrections to the earlier 0.3.0 names

Checked against 0.5.0. Confirmed unchanged: `Case.from_dict`, `from_json`, `to_dict`, `schema`, `check`, `files`, `leaf`; `Plant.from_dict`, `from_json`, `to_dict`, `check`, `summary`, `purpose`; `gm.plants.schema`, `names`, `get`, `capabilities`; `Module.describe`, `parameter_schema`; `gm.modules.names`, `categories`, `get`; `Study.from_dict`, `from_json`, `to_dict`, `schema`, `check`, `run`; `gm.study.minimize`, `sample`, `size`, `sensitivity`, `StudyResult`; `gm.evaluate.report`, `totals`, `capacities`, `requirements`, `verdict`, `compare`; `gm.units`; `gm.errors`. Corrections: `Plant.validate_params` is a `Module` method (inherited by `Plant`), not a plant-level validator; `Callback` is not public (section 6); `Case.check()` lists issues only for a built case, so missing and structural problems of a document are read from the error `from_dict` raises.

## MISSING, for the requests list (section 9)

1. Case schema section titles: none; closest is the backend's own label table keyed by the top-level schema property names.
2. Case series as `[time, value]` points: none; build from `leaf.series.time` and `.si`.
3. Module title as a field: none; closest `describe()["type"]` and `describe()["summary"]`.
4. Plant title (human label): none; closest `describe()["type"]`, with purpose and summary.
5. Plant `validate`, `from_spec`, `migrate`, and a no-build document check: none; closest `Plant.from_dict` (which builds in memory).
6. Per-method study settings schemas: none; closest `Study.schema()` flat plus `study.check()`.
7. Study progress callback: none for `Study.run` or the study functions.
8. Study cancel check: none; closest is terminating a worker process.
9. Daily coverage by source: none; closest is per-step `results.get(...)` summed by day in the backend.
