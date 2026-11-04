# Backend B3: Plant model and time series

## Goal

The API for building and editing the plant model, linking it to tags, importing and reading time series, and computing soft sensors.

## Context

- Follow the shared rules in `../docs/phases.md` (section "Rules for every phase") and the contracts in `../docs/contracts.md`.
- Needs B1. Read `../docs/feature-map.md`, domains `plant` and `timeseries`. Each use-case lists the legacy IDs; read those entries in the legacy inventories for behaviour to keep and bugs not to copy.
- **Before starting, add the routes for this phase to `contracts.md`** and tell the frontend; F3 and F4 build against them.

## Layout

```
src/api/v1/plant/       flowsheet  parameters  bindings  catalogue
src/api/v1/timeseries/  dashboard  trends  sources  availability  softsensors
```

## Steps

1. **plant/flowsheet:** palette from gemini's module registry (through `core/gemini`), save as a new plant version with a note, discard (reload latest), history (version list), start from the example plant.
2. **plant/parameters:** read and edit parameters of one module with dated versions; upload trajectory and tally (one tally upload only; the legacy app had two); parameters as they were on a date.
3. **plant/bindings:** link module variables to tags with dated versions, using gemini's `Bindings`.
4. **plant/catalogue:** catalogue entries (ESP pumps first) in postgres: list, add, edit, remove; fill a module's parameters from an entry.
5. **timeseries/sources:** historian connection (secrets never returned), data intervals, CSV import with documented columns into InfluxDB.
6. **timeseries/trends:** list tags of a project, series of tags over a time range with a step.
7. **timeseries/availability:** first and last timestamp per tag, in one query per project, not per tag.
8. **timeseries/softsensors:** Celery job that runs gemini replay over new data and writes calculated tags; a manual trigger route and an optional schedule.
9. **timeseries/dashboard:** dashboard URL from settings.

## Done when

- The example doublet can be built, edited, bound to tags and saved as versions through the API.
- A CSV import shows up in trends and availability; soft sensors compute calculated tags for it.

## Report back

What was built, the contract additions, legacy behaviour deliberately dropped, and open questions.
