# Backend B3a: B1 fixes and the plant model (Claude Code prompt)

You work in the backend repo at `/Users/sahand/Desktop/crust-team/backend`. B1 is done (branch `b1-foundations` in backend and infrastructure, not pushed). This prompt moves the work to `main`, fixes what the B1 report found, renames the Celery files, switches plant storage to gemini's JSON plant spec, and builds the plant domain: flowsheet (palette, templates, free editing of the spec, versions), equipment parameters, tag bindings and the equipment catalogue. The assistant (B2) and time series (B3b) are not part of this prompt.

Work step by step. Commit after each step.

**Status (2026-10-30 13:19):** the first run did section 0 items 2 and 3 (B1 on `main`, extra branches deleted) and step 1 (commits 9c37534 to d3f1486, migration 0005), then stopped because the gemini plant work (now part of gemini's "freeze and document interfaces" prompt) had not landed. On this run: do section 0 items 1, 4, 5 and 6, skip items 2 and 3 and step 1, and start at step 2. Where this prompt and `../docs/contracts.md` differ, the flowsheet fields `category` and `stream` in section 6 are wanted (they are in both now). An empty `FIRST_ADMIN_PASSWORD` stays allowed outside development (it means no admin is created). Commit `1135204` "Remove the old agent package name" on backend `main` is expected (Sahand's rename from swarmax to geomind); treat it and earlier commits as known, and apply the "commits you did not make" check only to commits that arrive during this run.

## 0. Branch and parallel sessions

**Branch rule (new, from Sahand):** in every repo except gemini, work, commit and push directly on `main`. No feature branches, no pull requests.

1. **At the start**, in both `backend` and `../infrastructure`: run `git status` and `git log -5`. If there are uncommitted changes, or `.tmp/session.lock` exists, stop and ask Sahand. Otherwise write `.tmp/session.lock` (time and a one-line note of this task) in the backend repo.
2. **Move B1 to main** in both repos: `git switch main`, `git merge --ff-only b1-foundations`. If the fast-forward fails, stop and ask. Then `git push origin main` in both.
3. **Delete the extra branches** in both repos, local and on `origin`: every branch other than `main` that is fully merged into `main` (`git branch --merged main`, `git branch -r --merged origin/main`). A branch that is **not** fully merged is never deleted: list it with its last commit and ask Sahand. Afterwards `git branch -a` shows only `main` and `origin/main` (plus any unmerged branches you reported).
4. **Other sessions** work in parallel on `../gemini`, `../geomind` and `../frontend`. That is fine; those repos are read-only for you. If gemini's API seems to differ from what you read earlier, read its docs again before assuming a bug.
5. **Before each commit:** `git status` again. Files you did not touch, or commits you did not make, mean another session is here: stop and ask. Never commit, revert or stash someone else's changes.
6. **At the end:** run the full fast suite, push `main` in every repo you committed to, delete `.tmp/session.lock`.

## 1. Read first

1. `AGENTS.md`, `docs/CONVENTIONS.md`, `docs/DEVELOPMENT.md` and the code B1 added (`src/core/gemini/`, `src/core/security/`, `workspace/projects`, `plant_versions`).
2. In `../gemini`: `AGENTS.md` and `.claude/docs/` (public API, modules, plants, types). Read only.
3. Section 6 of this prompt is the API contract for this phase. If `../docs/contracts.md` exists and differs on these routes, follow this prompt and report the difference.

The backend uses only gemini's public API: `import gemini as gm`, `gm.<name>`, `gm.plants.<name>`, `gm.errors.<name>`. Never an internal path.

## 2. Rules

Same as B1, repeated so this prompt stands alone:

- Features: `src/api/v1/<domain>/<feature>/{router,schemas,services,tasks}.py`, only the files a feature needs. One service function per use-case, named after it.
- Features never import each other; shared data goes through repositories in `src/core/clients/postgres/repositories/`.
- `gemini` is imported only in `src/core/gemini/`; the agent package only in `src/api/v1/assistant/runs/adapters/`. No physics formulas in the backend.
- Every route that touches a project uses `require_project`; every authenticated route uses `CurrentUser`.
- Simple, readable, just enough code; nesting at most 3; functions about 40 lines; guard clauses; full-word names; no dead or speculative code; no comments inside code (docstrings only).
- Times timezone-aware, UTC. Secrets never returned or logged.
- Tests: while working only the changed code and its importers, in parallel; full fast suite before each commit; never the network. New tests mirror `src/`. Temporary files in `.tmp/`.
- Update `AGENTS.md` and `docs/` in the same commit as the change.
- Subagents use lighter models (sonnet or haiku).
- If something is missing, unclear or risky, stop and say so.

## 3. Steps

### Step 1: B1 fixes

1. **Remove public signup and forgot-password**: routes, services, schemas, tests, docs. Users are created by an admin only.
2. **Revoke tokens** when a user's password changes or the user is deactivated: a `tokens_valid_after` time on the user (migration); access and refresh tokens issued before it are refused. One check, in the place that resolves `CurrentUser`.
3. **Route guard test**: a test lists every route of the app and fails unless it depends on `CurrentUser` or is in one explicit public list (login, refresh, health). Error message names the route.
4. **Placeholder admin password**: outside the development environment, startup refuses to run when `FIRST_ADMIN_PASSWORD` equals the value in `.env.example` or is shorter than 12 characters. Clear error message.
5. **Celery file names**: rename every `jobs.py` to `tasks.py` (Celery's default autodiscovery name) and update imports, Celery autodiscovery, the feature folder pattern in the docs, and the boundary test. In the docs, define the two words: a *task* is the Celery code in `tasks.py`; a *job* is the record a user sees (added later with its table).

Tests for each item. One commit per item is fine.

### Step 2: plants as specs

gemini now describes every plant as a **JSON spec** (format 2), built like Keras: `gm.Plant(name)`, `.add(type, name, **params)`, `.connect(a, b)`. There are no handwritten plant classes any more; templates and examples are spec files. The stored plant file is the spec:

```json
{"format": 2, "name": "doublet",
 "modules": {"res": {"type": "Reservoir", "params": {"depth": "2.5 km"}},
             "prod": {"type": "ProductionWell", "params": {}}},
 "connections": [{"source": "res.outlet", "target": "prod.inlet"},
                 {"source": "inj.outlet", "target": "res.inlet", "kind": "state"}],
 "bindings": {}, "param_history": {}}
```

Public names used (gemini's frozen interface list; read gemini's `.claude/docs/api.md` for the exact signatures): `gm.plants.from_spec(spec)`, `gm.plants.validate(spec) -> [{path, message, code}]`, `gm.plants.spec_schema()`, `gm.plants.templates()`, `gm.plants.from_template(name, parameters)`, `gm.plants.example(name)`, `gm.plants.migrate(old)`, `gm.plants.convert_legacy(folder)`, `gm.modules.names(category=None)`, `gm.modules.get(name)`, `Module.describe()`, `Module.parameter_schema()`, `gm.modules.get(name).validate_params(params)`, and for dated parameters and bindings `plant.set_params`, `plant.params_at`, `plant.param_history`, `plant.bindable`, `plant.set_bindings`.

**First check that it has landed:** `gm.plants.from_spec`, `gm.plants.validate` and `gm.plants.migrate` exist. If not, stop here after step 1, push, and report that this prompt continues once that gemini work has landed. Names that exist but raise `gm.errors.NotImplementedYet` are fine: build against them, mark the affected tests as expected to fail with that error, and list them in the report.

Then in `src/core/gemini/plant.py`:

- `validate_content(spec)`: `gm.plants.validate(spec)`; any problem is `422 plant_invalid` with `details = {"problems": [{path, message, code}]}`, all problems at once, paths as gemini gives them (`connections[1].target`).
- `load_plant(spec)`: validate, then `gm.plants.from_spec(spec)`. Remove B1's class-path rewriting, the `gemini.` prefix check and the class allowlist; gemini's validation decides.
- `example_plant()`: `gm.plants.example(...)` as a spec, with real values.
- `plant_versions.plant_type` becomes `name` (the spec's `name`), in a migration.
- Alembic **data migration** over `plant_versions`: each row through `gm.plants.migrate(content)`, then recompute `name` and `digest`. Rows already in format 2 are left as they are. The migration reaches gemini only through a function in `src/core/gemini/`.
- **Legacy import**: `convert_legacy(folder)` in `src/core/gemini/` over `gm.plants.convert_legacy`; `POST /workspace/projects/import` also accepts a legacy project zip (detected by its files), stored as version 1 with note "Imported from legacy project".

Tests: example spec round-trips unchanged (`to_spec(from_spec(x)) == x`); a migrated old row loads; a spec with a wrong port and an unknown type returns both problems with paths; legacy import of gemini's example legacy project.

### Step 3: core/gemini for the plant domain

Add to `src/core/gemini/` only what the routes in section 6 need, as plain functions over the stored spec, each going through gemini's public API:

```python
list_palette() -> list[dict]                       # gm.modules: type, title, category, summary
list_templates() -> list[dict]                     # gm.plants.templates(): name, title, description, purpose
build_template(name, parameters=None) -> dict      # gm.plants.from_template(...) as a spec
describe_plant(spec) -> dict                       # modules (id, type, title, category) and connections (source, target, stream, kind)
describe_module(spec, module, at=None) -> dict     # parameter_schema() with units, values at `at`, dated history, bindable names
set_parameters(spec, module, params, valid_from) -> dict   # plant.set_params, back to a spec
set_bindings(spec, module, bindings) -> dict                # plant.set_bindings, back to a spec
check_parameters(type_name, params) -> list        # gm.modules.get(type).validate_params(params)
```

- `describe_plant` takes category from `Module.describe()` of each module type and the stream type of each connection from gemini (the built plant's `describe()`), never from a backend table.
- Never re-implement gemini rules: when gemini has no public function for something, stop and report it instead of editing the spec by hand.
- Unknown module id: `404 module_not_found`.

Tests on gemini's example spec for each function.

### Step 4: plant/flowsheet

Feature `src/api/v1/plant/flowsheet/`. Routes in section 6.

- Because wiring is now data, the flowsheet can be edited freely: the client sends the **whole spec** (modules and connections added, removed or changed) and the backend validates it with gemini and saves it as a new version. Starting from a template is the same route with `template` instead of `spec`.
- **Diagram layout** is stored next to the spec, not inside it: column `layout` (json, null) on `plant_versions`, `{<module id>: {x, y}}`. It is not part of the digest, so moving boxes never counts as a plant change. `POST /plant/flowsheet` accepts it optionally; `PUT /plant/flowsheet/layout` replaces the layout of the latest version in place (with `base`, no new version). Layout entries for ids not in the spec are dropped.
- `POST /plant/flowsheet/validate` checks a spec without saving, so the editor can show problems while the user draws.
- **Concurrent edits:** every request that saves a version sends `base`, the version number it was built on (`null` for the first version). If the latest version is not `base`, answer `409 conflict` with `{"latest": n}` in `details`. This is how two tabs, or a user and the assistant, never overwrite each other.
- Saving identical content stays a `409 conflict` (B1 rule).
- `plant_version` on `project` keeps working.

### Step 5: plant/parameters

Feature `src/api/v1/plant/parameters/`. Read one module's parameters (optionally as they were at a date) and save new values with an optional `valid_from` date as a new plant version. Values are validated by gemini; a bad value is `422 plant_invalid` with gemini's field message.

Trajectory and tally uploads (legacy PLT-05, PLT-06) are not in this prompt: report how gemini stores them (which module, which parameter, what shape), so the next prompt can add one upload route each.

### Step 6: plant/bindings

Feature `src/api/v1/plant/bindings/`. Read one module's bindings and the names it can bind (controls, boundaries, inlets with their fields, measured, state); replace them as a new plant version. A binding is `{column, unit}`; `column` is the tag name in time series (B3b). Units are validated by gemini.

gemini's bindings carry no dates. History of the links is the plant version history; "links as they were on a date" means the version that was latest at that date. Report if gemini plans dated bindings.

### Step 7: plant/catalogue

Feature `src/api/v1/plant/catalogue/`, model and repository `CatalogueEntry`:

```text
catalogue_entries
  id            uuid
  kind          text, a gemini module registry name ("ESP"), checked against gemini
  name          text, unique together with kind
  manufacturer  text null
  params        json, validated with check_parameters(kind, params)
  created_by    fk users
  created, updated  timestamptz
```

- The catalogue is shared by all projects. Any signed-in user may read it; only an admin may add, edit or remove entries.
- Fill a module from an entry: `POST /plant/parameters/fill` copies the entry's `params` into the module as a new dated parameter entry (step 5's rules, plus: the module's type must equal the entry's `kind`, else `409 conflict`).

### Step 8: docs and contract

- `AGENTS.md` and `docs/`: the plant domain, the `base` rule for saving versions, task versus job, plants as specs, the route guard test.
- `../docs/contracts.md`, if it exists: do not edit it; report differences only.

## 4. Done when

- `main` holds B1 and this work in backend and infrastructure, pushed; merged extra branches are deleted locally and on `origin`.
- Every route in section 6 works and is tested, on gemini's example plant.
- Old plant content is migrated to the spec by the data migration; invalid specs are refused with every problem and its path.
- The route guard test, the boundary test and the full fast suite pass.
- Docs describe the new state.

## 5. Report back

- What was built, step by step, with commits.
- Whether gemini's plant spec work had landed, which names still raise `NotImplementedYet`, and anything the backend still lacks.
- Whether connections, declaration schemas, bindable names and dated parameters came from gemini's public API or from editing the content dict.
- Whether legacy import was built.
- How gemini stores trajectory and tally.
- Contract differences, frontend notes, risks, and whether you met another session's changes.

## 6. API contract for B3a

General rules as in B1: base `/api/v1`, JSON, UTC times, error body `{"error": {"code", "message", "details"}}`, lists `{"items", "next"}` with `?cursor=` and `?limit=`, creates answer `201`. New codes: `plant_not_found` (project has no plant version yet), `module_not_found`, `entry_not_found`.

Shapes:

```text
version    = {number, note, author: {id, name}, created}
spec       = gemini's plant spec, format 2 (see step 2), stored and returned unchanged
template   = {name, title, description, purpose}       purpose: heating, cooling or both
palette    = {type, title, category, summary}          one module type from gemini's registry
flowsheet  = {project, version, spec, layout,
              modules: [{id, type, title, category}],
              connections: [{source: "<id>.<port>", target: "<id>.<port>", stream, kind}]}
             category: the module's gemini category (icon, palette group, layout)
             stream: the stream type of the connection, from gemini (colour)
             kind: "state" for a connection that closes a loop, else null
             layout: {<module id>: {x, y}} saved by the editor, or null (the frontend lays out automatically)
problem    = {path, message, code}                     path into the spec, e.g. "connections[1].target"
parameters = {module, type, schema, values, history: [{valid_from, params}]}
             schema: JSON schema of the module's parameters, each property with "unit"
             values: effective at ?at= (or latest)
bindings   = {module, type, bindable: {controls: [name], boundaries: [name],
              inlets: {port: [field]}, measured: [name], state: [name]},
              bindings: {controls: {name: binding}, boundaries: {...},
              inlets: {port: {field: binding}}, measured: {...}, state: {...}}}
binding    = {column, unit}
entry      = {id, kind, name, manufacturer, params, created, updated}
```

### plant/flowsheet

| Method | Path | Body → Response |
|---|---|---|
| GET | `/plant/flowsheet/palette?category={name?}` | → list of `palette` |
| GET | `/plant/flowsheet/templates` | → list of `template` |
| GET | `/plant/flowsheet?project={id}` | → `flowsheet` of the latest version; `404 plant_not_found` if none |
| POST | `/plant/flowsheet` | `{project, base, note, spec, layout?}` or `{project, base, note, template, parameters?}` → `201 flowsheet` (new version) |
| PUT | `/plant/flowsheet/layout` | `{project, base, layout}` → `flowsheet` (latest version's layout replaced; no new version) |
| POST | `/plant/flowsheet/validate` | `{spec}` → `{problems: [problem]}` (empty when valid; nothing saved) |
| GET | `/plant/flowsheet/versions?project={id}` | → list of `version`, newest first |
| GET | `/plant/flowsheet/versions/{number}?project={id}` | → `flowsheet` of that version |

### plant/parameters

| Method | Path | Body → Response |
|---|---|---|
| GET | `/plant/parameters?project={id}&module={id}&at={time?}` | → `parameters` |
| POST | `/plant/parameters` | `{project, base, module, params, valid_from?, note}` → `201 version` |
| POST | `/plant/parameters/fill` | `{project, base, module, entry, valid_from?, note}` → `201 version` |

### plant/bindings

| Method | Path | Body → Response |
|---|---|---|
| GET | `/plant/bindings?project={id}&module={id}` | → `bindings` |
| POST | `/plant/bindings` | `{project, base, module, bindings, note}` → `201 version` |

### plant/catalogue

| Method | Path | Body → Response |
|---|---|---|
| GET | `/plant/catalogue?kind={name?}` | → list of `entry` |
| POST | `/plant/catalogue` | admin, `{kind, name, manufacturer?, params}` → `201 entry` |
| PATCH | `/plant/catalogue/{id}` | admin, `{name?, manufacturer?, params?}` → `entry` |
| DELETE | `/plant/catalogue/{id}` | admin → `204` |

Rules for every save: `base` must equal the latest version number (`null` when there is none), else `409 conflict` with `{"latest": n}` in `details`; identical content is `409 conflict`; gemini validation failures are `422 plant_invalid` with `details = {"problems": [problem]}`. `module` in the parameters and bindings routes is a module id from the spec.
