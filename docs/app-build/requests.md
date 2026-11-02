# Requests for gemini and geomind

Collected during the app build (section 9 of `app-frontend-backend.md`). Nothing here is blocking: no route returns 501 for these except `plant/parameters/fill`, which waits for the catalogue.

## gemini (0.5.0)

- [gemini] Daily coverage by source
  Needed by: `GET /design/results/{id}`, Results days strip
  Today: `gm.evaluate.totals` gives whole-window ratios only
  Wanted: `gm.evaluate.coverage(plant, case, results) -> [{date, source: geothermal|backup|short}]`
  Blocking: no (worked around: `coverage` is null, the strip says "not available")

- [gemini] Study progress callback and cancel check
  Needed by: `design/study` progress bar and cancel
  Today: `Study.run` and `gm.study.*` take neither; `gm.simulate` has `callbacks`, `Callback` is not exported
  Wanted: `on_progress(done, total)` and `should_cancel()` keyword arguments on `Study.run` and `gm.study.*`
  Blocking: no (worked around: progress stays 0 of 1, cancel terminates the worker)

- [gemini] Settings schema per study method
  Needed by: New study dialog
  Today: `Study.schema()` is flat with a `method` enum
  Wanted: `Study.schema(method)` returning only the fields of that method
  Blocking: no (worked around: all kinds share the flat schema)

- [gemini] Per-step system series
  Needed by: `GET /design/results/{id}` `series`
  Today: no output identifies the heat and cold delivered at the plant edge
  Wanted: `Results.series("heat_delivered" | "cold_delivered") -> [{time, value, unit}]`
  Blocking: no (worked around: `series` is `[]`)

- [gemini] Titles
  Needed by: palette, templates, KPI tiles, constraints, Problem tabs
  Today: `describe()["type"]` and `["summary"]`; report figures and requirements have names only; `Case.schema()` has no section titles
  Wanted: `title` in `Module.describe()`, plant `describe()`, report values, requirements, and on each top-level property of `Case.schema()`
  Blocking: no (worked around: class names and humanised names)

- [gemini] Plant migration
  Needed by: importing old plant files
  Today: `old_format` is raised
  Wanted: `gm.plants.migrate(document) -> document`
  Blocking: no (old documents are refused with `plant_invalid`)

- [gemini] Plant structure without a private form
  Needed by: `GET /plant/flowsheet`
  Today: the backend reads `to_dict(structure=True)`
  Wanted: a public `plant.structure() -> {modules, connections}`
  Blocking: no

- [gemini] Case series listing
  Needed by: `GET /design/case/series`
  Today: the backend walks the document for `{file, column}`
  Wanted: `case.series() -> [{path, file, column, unit}]`
  Blocking: no

- [gemini] Missing parameters per module
  Needed by: `GET /plant/parameters`
  Today: the backend filters `plant.check()` by path
  Wanted: `plant.missing(module) -> [{path, message}]`
  Blocking: no

## geomind

- [geomind] Chat-scoped artifact methods not released yet
  Needed by: the second message of a chat reading what the first run produced
  Today: `RunStore` has no `save_chat_artifact` / `load_chat_artifact`
  Wanted: both on the protocol and in `gd.testing.check_run_store`
  Blocking: no (the backend implements them, tested directly). An adaptation commit is expected on origin main.

- [geomind] Replacement for `gm.plants.validate`
  Needed by: `geomind/tools/gemini/plants.py:96` at eeb80d9
  Today: the call fails on gemini 0.5.0, where `validate` was removed on purpose
  Wanted: `Plant.from_dict` plus `check()`
  Blocking: yes for the design tools until the adaptation commit lands

- [geomind] Record studies and results that agents run
  Needed by: Study and Results pages
  Today: only `size_plant` and `optimize` store `design/<name>`, `simulate` stores `result/<id>`; sample, sensitivity and compare store nothing
  Wanted: an event or hook carrying kind, settings and result
  Blocking: no (agent studies do not appear as rows)

- [geomind] Per-project token budget
  Needed by: section 5.4 hooks
  Today: `TokenBudget` counts the run tree
  Wanted: a budget that takes a project total
  Blocking: no (worked around: `ASSISTANT_RUN_MAX_TOKENS` per run)

- [geomind] `RunResult.message`
  Needed by: `run.error.message`
  Today: on `run.finished` only
  Wanted: a `message` field on `RunResult`
  Blocking: no

- [geomind] `load_events` off the event loop
  Needed by: the database `RunStore`
  Today: `engine.resume` calls `store.load_events` directly
  Wanted: call it through `asyncio.to_thread`, like `save_event`
  Blocking: no (the backend warms the store first)

- [geomind] Cancel a run waiting on a request
  Needed by: `POST /assistant/runs/{id}/cancel`
  Today: `aresume()` without a request id fails while a request is pending
  Wanted: `aresume(cancel=True)`, or `Cancellation` honoured without an answer
  Blocking: no (the backend resumes with a stand-in answer)

- [geomind] Agents per run
  Needed by: Runs page Agents column
  Today: no list on the run
  Wanted: dotted agent paths from `gd.runlog` summary
  Blocking: no (the column shows the loop)
