# Backend design proposal (draft 1, 2026-10-30)

Answers to the nine open questions in [brief.md](brief.md), for discussion with Sahand. Nothing here is final until he agrees. Every name has its reason next to it.

Facts checked in gemini `refactor` (commit `80cd26b`, 2026-10-30 02:21) that shape this design:

- `Module.to_dict()` returns `{"version": 1, "plant_type": "<class path>", "modules": {path: {...}}}`. Each module entry already holds `params`, `fluid`, `param_history` (a list of `DatedParams {valid_from, params}`), `param_overrides`, `bindings` (`ModuleBindings`: controls, boundaries, inlets, measured, state, each `{column, unit}`) and `boundary`.
- `Plant.from_dict(data)` is a classmethod: it builds the handwritten class named by `plant_type`, then demands that the stored module paths equal the class's paths exactly. So **a stored file can fill a plant but cannot change its wiring.**
- gemini has a legacy converter (`gemini/core/legacy/convert.py`), so legacy project files can become the new format.

---

## 1. Plant model storage

**Recommendation: one immutable row per version, holding gemini's `to_dict()` output unchanged. No split tables.**

```text
plant_versions
  id            uuid
  project_id    fk projects, on delete cascade
  number        int, unique with project_id, 1, 2, 3 ... (what the user sees: "version 7")
  plant_type    text, copied from content for listings
  content       jsonb, exactly Plant.to_dict()
  digest        text, sha256 of the canonical JSON; saving identical content is refused (no empty versions)
  note          text, the change note (legacy PLT-01)
  author_id     fk users
  created       timestamptz (UTC)
```

- **Why one JSON:** gemini already versions parameters by date (`param_history`) and stores bindings per module. Splitting them into tables would be a second format that must be kept in sync with gemini forever. gemini validates the whole file on load, so a stored version is either valid or refused.
- **Two kinds of "version", kept apart by name:**
  - *plant version* (`number`): a saved edit of the model, made by a person or the assistant. Like a commit.
  - *dated parameters* (`valid_from` inside the content): the physical history of the equipment ("the pump was replaced on 2025-03-01"). Like a fact about the world.
  Editing a parameter with a date means: load the latest version, add a dated entry through `core/gemini`, save a new plant version.
- **Latest** = the highest `number`. Rows are never updated. Discard (PLT-02) = reload the latest. History (PRJ-07) = the list without `content`.
- **Queries such as "parameters on a date" (PLT-08)** load the plant through `core/gemini` and ask gemini; no SQL over the JSON.
- A new project has no version. The first one comes from "start from an example plant", an import, or the assistant.
- **Size:** a doublet is tens of kilobytes. If trajectories and tallies make it large, they move to MinIO with a reference in the parameter, later and only if measured.

**Risk for B3 (flowsheet), to decide now:** because gemini plants are handwritten classes, the browser cannot "draw" new wiring that gemini can load. The flowsheet in B3 therefore means: pick a plant template (a gemini plant class), switch its optional units on or off, and edit parameters and bindings. Free drawing needs gemini to build a plant from a graph, which it does not do. This matches the geomind design (agents also pick and size templates). Recommended; free drawing only after the hackathon.

## 2. core/gemini

The only backend folder that imports `gemini`. Name kept from the brief: it says exactly which library it wraps.

```text
src/core/gemini/
├── plant.py       B1: content ↔ gemini plant
├── templates.py   B3: plant templates and module palette
└── compute.py     B3/B4: named calculations (replay for soft sensors, nodal, Hall, pump)
```

B1 API of `plant.py` (plain functions, no class):

```python
load_plant(content) -> gm plant          # resolves plant_type, calls from_dict
dump_plant(plant) -> dict                # to_dict
validate_content(content) -> dict        # load + dump; raises PlantContentError (stable code plant_invalid)
example_plant() -> dict                  # content of gemini's example doublet
```

- **Security:** `plant_type` comes from stored JSON and names a class to import. `load_plant` only resolves class paths inside the `gemini` package and only classes that are plants; anything else is `plant_invalid`. Never `importlib` on an arbitrary string.
- gemini errors become one backend error with code `plant_invalid` and gemini's message in `details`, so the browser can show it.
- **Where calculations run:** the API process only loads and validates (milliseconds). Anything that simulates (replay, nodal, calibration) runs in a Celery worker through `compute.py`. API and worker use the same image with gemini installed; only the command differs.

## 3. Runs and events

```text
chats          id, project_id, title, state jsonb null, created_by, created
messages       id, chat_id, role (user|assistant), content, run_id null, created
runs           id, chat_id, message_id, status, loop null, stop_reason null, error null,
               request jsonb null (the pending request while waiting),
               input_tokens, output_tokens, cost, created, started null, ended null
run_events     run_id, sequence, type, agent, parent, public bool, data jsonb, created
               primary key (run_id, sequence)
run_artifacts  run_id, key, content_type, data bytea, created         primary key (run_id, key)
```

- **Names:** `run_events` uses geomind's word (no checkpoints since interface 2.3; recovery reads `load_events`), so `RunStore.save_event` writes `run_events` with no translation. `chats.state` is the problem state (`save_state`/`load_state`); one column, because there is one state per chat.
- **One source of truth:** every geomind event (public and internal) is a row. The run log (`GET /runs/{id}/log`) is `gd.runlog(events)` over the stored rows, built on request. No separate `llm_calls` or `tool_calls` tables: geomind already defines the log, the backend only stores it.
- **Usage totals** on `runs` are updated from each `usage` event, so lists need no aggregation.
- **The assistant message** is written when the run ends (`RunResult.answer`), with `run_id`, so the chat history and `load_history` stay simple.
- **Ordering:** only one job works on a run at a time, so the store adapter numbers events itself: it reads `max(sequence)` once at job start, then counts up. The SSE `id` is this `sequence`.
- **Write, then publish:** each event is inserted in Postgres first, then published to Redis channel `runs:{id}`. The SSE route subscribes to Redis first, then reads public rows with `sequence > Last-Event-ID` from Postgres, sends them, then sends live messages, skipping any `sequence` already sent. No gap and no duplicate on reconnect.
- **State changes are guarded:** every status change is a conditional update (`... where status = 'waiting'`). Answering a run that is not waiting, or with the wrong request id, is `409 run_not_waiting`. This stops two resumes of one run.
- **Cancel:** the route sets Redis key `runs:{id}:cancel` (with a TTL) and, for a queued or waiting run, sets `cancelled` at once. A running run stops at its next step through `gd.hooks.Cancellation`.
- **Crash:** Celery runs with late acknowledgement; a job that finds its run still `running` calls `run.resume()` (geomind continues from its log). A hard time limit marks the run `failed` with `stop_reason=timeout`.
- **Retention:** keep everything while the hackathon runs; the log is a deliverable. Rows go with their project (`on delete cascade`). A retention rule for internal events comes later, when there is real data.

## 4. Jobs

**One pattern, in `src/core/jobs/`, used by every long calculation.** Built in B2 with runs as its first user, extended with a table in B3.

- A Celery base task that gives every job: a time limit (soft then hard), a cancel check (`jobs:{id}:cancel` in Redis), progress reporting, and failure capture (status `failed`, error code and message stored, full traceback only in the log).
- B3 adds the general table and feature for soft sensors and well performance:

```text
jobs   id, project_id, kind ("softsensors.compute", "performance.nodal" ...), status
       (queued|running|done|failed|cancelled), progress 0..1, message, result jsonb, error,
       created_by, created, started, ended
```

  Feature `system/jobs` (feature map: Platform, Background Jobs): `GET /system/jobs/{id}`, `POST /system/jobs/{id}/cancel`. A feature route that starts a job returns `202 {job}`.
- Runs keep their own table, because they have more states (`waiting`) and events, but use the same base task.
- Large results go to MinIO with a reference in `result`, never into Redis.

## 5. Access

- Roles stay `admin` and `member`. The first admin is created at startup from settings (AUTH-05).
- A project has one owner. **Rule: the owner or an admin may read and change a project; nobody else.**
- All of it in one dependency, `core/security/access.py: require_project(project_id, user)`, used by every route that takes a project or anything inside one (chat, run, document). A run is reached through its chat and project, so the check covers it.
- Not found and forbidden both answer `404 project_not_found` for a non-admin, so ids cannot be probed.
- **Sharing** (legacy ADM-01 "assign projects to users"): not in the hackathon. Later it is a `project_members` table and a change inside `require_project` only. No route changes.
- Users are deactivated (`active=false`), never deleted, so authorship in versions and runs stays valid.

## 6. Documents and search (after B2)

```text
documents   id, project_id, title, filename, content_type, size, digest, status
            (uploaded|indexing|indexed|failed), error, created_by, created
```

- Files in MinIO: bucket `gemini`, key `projects/{project_id}/documents/{document_id}`.
- Upload stores the file and starts a job `documents.index`: extract text, split into chunks, embed, write to ChromaDB collection `project-{project_id}` with `document_id` and chunk number.
- `Workspace.documents(project_id, query)` = one ChromaDB query, top 5, returned as `[{id, title, text, score}]`. Empty list until documents exist (B2).
- Embeddings: ChromaDB's local default model (no API cost, no keys, same answer offline). To confirm.

## 7. Time series (B3)

- **Values in InfluxDB, metadata in Postgres.** Bucket `timeseries`, measurement `tag`, tag keys `project` and `name` and `kind` (`measured`, `filtered`, `calculated`), one field `value`.
- `tags` table in Postgres: `project_id, name, kind, unit, description`. A binding in gemini (`{column, unit}`) points at a tag by `name`.
- **CSV import:** wide format, first column `time` (ISO 8601 with offset; naive times refused), one column per tag, header `name [unit]`, for example `time,WHP-01 [bar],FT-01 [m3/h]`. Unknown tags are created as `measured`. One documented format; the legacy app guessed.
- **Historian:** a `sources` row (type `aveva`, URL, user, secret encrypted with a key from settings). The secret is never returned: responses carry `has_secret: true`. Reading goes through a small reader protocol in `core/clients/`, InfluxDB first, AVEVA second.
- **Availability:** one Flux query per project grouped by `name` (`first()` and `last()`), not one per tag.

## 8. Tests

```text
tests/
├── api/v1/<domain>/<feature>/test_<usecase>.py    mirrors src/api/v1
├── core/...                                        mirrors src/core
├── test_boundaries.py                              import rules (AST scan)
└── conftest.py                                     app, client, users, tokens, project
```

- **Postgres:** fast tests use SQLite in memory with portable column types (`JSON` with a `JSONB` variant for Postgres); a small `postgres` marker runs the repository tests against the compose Postgres before merging. To confirm against how the current tests already work.
- **Redis:** `fakeredis`. **Celery:** tests call the job function directly; no broker.
- **gemini:** the real package with its example doublet; it is local and fast. Simulations that take seconds are marked slow.
- **geomind:** until S1, a stub with `gd.Run`'s shape that emits the contract events; after S1, the real `gd.Run` with `FakeLLM`.
- **Boundary test:** only `src/core/gemini/` imports `gemini`; only `src/api/v1/assistant/runs/adapters/` imports `geomind`; no feature imports another feature.

## 9. Changes proposed to contracts.md

1. **Refresh route listed:** `POST /identity/authn/refresh` `{refresh_token}` → `{access_token, refresh_token}`.
2. **`user` gets `active`;** `PATCH /identity/users/{id}` takes `{role?, name?, active?}`.
3. **`project.owner` is `{id, name}`,** so the list needs no second call. `project` gets `plant_version` (latest number or `null`).
4. **`run` gets `request` and `error`:** `request` holds the pending request while `waiting`, so a reloaded page shows the question without the stream.
5. **SSE and auth:** the browser's `EventSource` cannot send an `Authorization` header. The frontend reads the stream with `fetch` (for example `@microsoft/fetch-event-source`) and sends the bearer token. No tokens in URLs. The frontend thread must know this.
6. **Chat:** add `PATCH /assistant/chat/{id}` `{title}` and `DELETE /assistant/chat/{id}`.
7. **Stable error codes listed:** `unauthorized`, `forbidden`, `not_found` and `<thing>_not_found`, `validation_failed`, `conflict`, `run_not_waiting`, `plant_invalid`, `rate_limited`, `internal`.
8. **Export zip layout fixed:** `project.json`, `plant/<number>.json` (each version's content and note), later `documents/`. Import also accepts a legacy project zip, converted by gemini's legacy converter through `core/gemini`.

## Impact on the phases

- **B1:** identity/users, workspace/projects (with export and import), `plant_versions` and `core/gemini/plant.py`, `require_project`, error codes, boundary test, compose. No plant routes yet (B3).
- **B2:** chats, runs, events, checkpoints, artifacts, `core/jobs` base task, adapters, SSE.
- **B3:** flowsheet as templates, parameters and bindings through `core/gemini`, `jobs` table and `system/jobs`, time series, documents.
- **B4:** unchanged.
