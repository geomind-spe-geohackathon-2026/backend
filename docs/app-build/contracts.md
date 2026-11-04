# Contracts between the repos

Version 1.1.7 (2026-11-04). From 1.0.0 the backend and this contract share one version, `v<major>.<minor>.<patch>` (`src/version.py`, the OpenAPI `info.version`, `GET /system/health` `version`, and a `v<version>` tag on `main`), the same scheme as the frontend: for now every release stays on 1.1 and raises only the patch. 1.0.0 is the contract as it stood at number 52; the numbers below are the history before it, and the next changes are listed in `CHANGELOG.md`.

Version 52 (additive): the live event table has its `study.recorded` row, the event geomind has sent since 0.4.0. Version 51 (additive): `POST /design/study` takes an optional `plant_version`, the number of the plant version to study; without it the study takes the latest, as before. A study has `plant_pinned`, true when the version was chosen; a blocked study that starts later keeps a chosen version and takes the latest otherwise. Version 50 (additive): `tool.finished` has `problem`. Version 49 (additive): a new size in `POST /plant/parameters/plant` gives each added module the values of a module of its class. Version 48 (additive): `WS /assistant/runs/{id}/stream` carries the same events as `GET /assistant/runs/{id}/events`. Version 47: the model example in `step.started` is a DeepSeek id; the assistant runs on DeepSeek only. Version 46 (additive): `POST /plant/parameters/plant` also takes `values`, path to `{value, unit}`; a new size drops the values of modules the plant no longer has. Version 45 (additive): `GET /plant/parameters/plant` and `POST /plant/parameters/plant` read and set the search ranges no module holds, such as `size.doublets`, by the plant file's path. Version 44 (additive): `GET /plant/parameters` has `search`, name to `{min, max, unit, units}` of what a study can search, in the unit the value shows in and in each other unit, converted by gemini; `POST /plant/parameters` takes `ranges`, name to `{min, max, unit}`, set with `plant.set_range`, both empty removes one. Version 43 (additive): the case schema marks `time.start` and `time.end` with `x-date`. Version 42 (additive): `GET /plant/parameters` has `ranges`, the names under the module that a study can search over a range, from `gm.plants.capabilities()` mapped to every module of the same class; empty for a free plant. Version 41: fitted to gemini 0.5.4. A tornado row has `feasible_low` and `feasible_high`, a spread row has `feasible`, the number of feasible draws; each is null on a result stored before 0.5.4. Version 40 (additive): a report's `flowsheet.modules` have `settings`, a digest of the module's values; the process diagram merges modules only when type, connections and `settings` are all equal. Version 39 (additive): `POST /reporting/design/export` takes `flowsheet_full_svg`, drawn into the appendix on its own landscape PDF page; `flowsheet_svg` is now the simplified process diagram. Version 38 (additive): `GET /assistant/chat/{id}/files/{name}` returns a case file the assistant wrote. Version 37 (additive): a result has `role`, `doublets`, `depth`, `depth_unit`; a comparison has `spreads`, one row per uncertainty study on a compared design. Version 36: fitted to gemini 0.5.3 and geomind 0.4.1. `study/kinds` comes from `gm.study.kinds()` and has `use`; `size` is `use: prepare`. `missing` comes from `gm.case.missing`; `POST /design/case/validate` adds `warnings`, which never block. Metric titles are gemini's. The case schema carries `x-quantity`, `x-units`, `x-limits`, `x-fraction`, and the requirement item `x-roles` and `x-time-units`. Report section `capex`. Version 35 (additive): report sections hold Markdown images with an SVG data URI (key figures, flowsheet, days covered, demand and supply). Version 34 (additive): report sections `summary`, `coverage`, `findings`, `appendix`; `design` is short and its module table moved to `appendix`. Version 33 (additive): `DELETE /design/case/files/{name}?project&base` saves a version without the file. Version 32 (additive): a result detail has `tornado` and `spread`, null for other kinds. Version 31 (additive): `POST /design/results/{id}/adopt` saves a result's design as the next plant version. Version 30 (additive): `POST /design/case/validate` adds `plant_missing` and `has_plant`. Version 29 (additive): a constraint has `module`, `value`, `unit`, `limit` (text with its direction), `margin`, `near` and `worst`; a result stored without coverage gets it on first read. Version 28 (additive): `GET /workspace/documents/formats` lists the suffixes an upload may have; a template has `modules` and `categories`. Version 27 (additive): `POST /workspace/projects/{id}/case/copy` copies another project's latest case into a project without one. `GET /system/health` has `assistant: model|scripted`. Version 26: fitted to gemini 0.5.2. Study `progress` counts gemini's trials and a cancel stops the study between trials, with no result; a kind without trials goes from 0 of 1 to its end. `result.coverage` is `{heating: [day], cooling: [day]}` or null, `day = {date, source, demand, geothermal, backup, short, failed_steps}` from `gm.evaluate.daily_coverage`. A capacity has `kind`, `peak`, `peak_unit` and `share`, and `title` is the module id; `result.sizes` holds ratings that are lengths. Version 25 (additive): fitted to gemini 0.5.1 and geomind 0.4.0. `project.budget = {max_tokens, max_cost}`, set with `PATCH /workspace/projects/{id}` (`name` and `budget` both optional); a null cap is no cap, and no cap means no budget hook. A `study.recorded` event adds a `done` study with `started_by.kind = agent` and no result. Readers skip event types they do not know. Version 24 (additive): `project` has `chats` and `runs`, counts of the project's chats and runs. Version 23 (additive): `study/kinds` adds `size`, written as method `run` with `prepare: ["size"]`, and every other method takes `prepare` in its settings. Version 22 (additive): `flowsheet.structure`; `POST /plant/flowsheet/validate` takes optional `project` and checks against its latest case; `GET /reporting/design/parts`; `reason` on KPIs and capacities; a chat without a title takes one from its first message; `POST /design/case/validate` takes `project`. Version 21 (additive): `GET /plant/flowsheet/ports`; `POST /workspace/projects` takes optional `case_from`; a buffered `text.delta` carries `buffered: true` and replaces the step's streamed text; `activity.link.route` is a project-relative frontend route. Version 20: fitted to gemini 0.5.0, which has no spec format 2: `spec` is gemini's own plant document (`gm.plants.schema()`, checked with `Plant.from_dict` and `check()`), templates are `gm.plants.names()`, palette and template `title` is the gemini class name; case sections are the schema's top-level properties; `study/kinds` lists gemini's `method` values and all share `Study.schema()`; `progress` stays `{done: 0, total: 1}` until the study ends because gemini has no progress callback, and cancel terminates the worker; `coverage` is `null` until gemini publishes daily coverage by source; chat-scoped artifacts implemented by the backend ahead of geomind. Version 19: HTTP API section from the app-build prompt (versions 16 to 19): plant on gemini spec format 2 (module `id`, `spec`, `layout`, palette, validate), new domains `design/case`, `design/study`, `design/results`, `reporting/design`, `workspace/overview`, `workspace/documents`, `assistant/usage`, run log export, project `progress` and `case_version`, codes `case_invalid`, `missing_inputs`, `not_implemented`, `Workspace.case` and chat-scoped artifact methods in section 3 (2.6). Version 15: internal `compaction` event (geomind S2). Version 14: `step.finished` carries `text`, the step's full assistant text. Version 13: how `RunStore` stores events (full `event.to_dict()`, not `data()`), nested runs share the root run's log, `text.delta` is stream-only from S2. Version 12: flowsheet modules carry `category`, connections carry `stream`. Version 11: plant domain routes (backend B3a, frontend F3) in section 1. Version 10: creates answer 201, code `unavailable` (503), refresh tokens rotate (from the B1 report). Version 9: geomind drops checkpoints (the event log is the only run state): `save_checkpoint`/`load_checkpoint` and the internal `checkpoint` event are removed. Version 8: `step.started.model`, option answers and `run.error` from geomind defined. Version 7: assistant routes for B2 (runs list per project, chat problem state, the user message carries its run). File version, raised on every change: section 1 from the backend design (refresh, `active`, project owner and plant version, run request and error, chat edit and delete, error codes, `?cursor=`, validation details); sections 2 and 3 from the geomind design (section 3 keeps its own interface version, now 2.2). Covers steps 1 and 2 of every repo. Later steps add their routes here before they start.

## 1. HTTP API (frontend ↔ backend)

- Base: `/api/v1`. JSON. Times are ISO 8601 with a timezone, UTC.
- Path = `/<domain>/<feature>/...`, the same names as the folders in both repos.
- Auth: bearer access token from `identity/authn`, renewed with `POST /identity/authn/refresh`. A refresh token works once: the response carries a new one, which the client must keep. Tokens never go in URLs.
- Live events (section 2) are read with `fetch` and the bearer header (for example `@microsoft/fetch-event-source`), because the browser's `EventSource` cannot send an `Authorization` header.
- Errors: `{"error": {"code": "<snake_case>", "message": "<human text>", "details": {...}}}` with a matching HTTP status. Codes are stable; messages may change.
- Lists: `{"items": [...], "next": "<cursor or null>"}`; the next page is `?cursor=<next>` (optional `?limit=`, default 50).
- Stable error codes: `unauthorized` (401), `forbidden` (403), `not_found` and `<thing>_not_found` (404), `validation_failed` (422, `details = {"fields": {"<field>": "<message>"}}`), `conflict` (409), `run_not_waiting` (409), `plant_invalid` (422, `details.problems`), `case_invalid` (422, `details.problems`), `missing_inputs` (422, `details.missing = [{path, message}]`), `rate_limited` (429), `unavailable` (503, a backing service such as Redis is down), `not_implemented` (501), `internal` (500). Every `POST` that creates something (user, project, import, chat, message, document, case, study, plant version) answers `201`. Every save of a versioned thing takes `base` (the latest version number, or `null`) and answers `409 conflict` with `details.latest` when stale; identical content is `409 conflict`. A project the caller may not see answers `404 project_not_found`, the same as a missing one.

### identity

| Method | Path | Body → Response |
|---|---|---|
| POST | `/identity/authn/login` | `{email, password}` → `{access_token, refresh_token, user}` |
| POST | `/identity/authn/refresh` | `{refresh_token}` → `{access_token, refresh_token}` |
| POST | `/identity/authn/logout` | → `204` |
| GET | `/identity/me` | → `user` |
| POST | `/identity/me/password` | `{old_password, new_password}` → `204` |
| GET | `/identity/users` | admin → list of `user` |
| POST | `/identity/users` | admin, `{email, name, password, role}` → `user` |
| PATCH | `/identity/users/{id}` | admin, `{role?, name?, active?}` → `user` |

`user = {id, email, name, role, active}`, `role` is `admin` or `member`. Users are deactivated, never deleted; an inactive user cannot sign in.

### workspace/projects

| Method | Path | Body → Response |
|---|---|---|
| GET | `/workspace/projects?search=` | → list of `project` (`search` filters by name) |
| POST | `/workspace/projects` | `{name, case_from?}` → `201 project`; `case_from` is a project id you may read: its latest case and the files it names become version 1 of the new project (`404 project_not_found` otherwise, `404 case_not_found` if it has no case) |
| GET | `/workspace/projects/{id}` | → `project` |
| POST | `/workspace/projects/{id}/case/copy` | `{case_from}` → `project`; 409 when it has a case |
| PATCH | `/workspace/projects/{id}` | `{name?, budget?: {max_tokens, max_cost}, memory?: "on"\|"off", mcp?: [MCP server id]}` → `project`; an unknown MCP server id is `422` with `details.fields.mcp` |
| DELETE | `/workspace/projects/{id}` | → `204` |
| GET | `/workspace/projects/{id}/export` | → zip file |
| POST | `/workspace/projects/import` | multipart `file` → `project` |

`project = {id, name, owner: {id, name}, plant_version, case_version, created, updated, progress, chats, runs, budget, memory, mcp}`; `memory` is `"on"`, `"off"` or `null` (not chosen yet; a run then uses no memory); it switches the agents' own memory (lessons and reviewed designs, written by geomind only and not shown in the app), never the Knowledge, and `POST /workspace/projects` takes `memory` and `mcp` too; `plant_version` and `case_version` are the latest version numbers or `null`; `progress = {case, plant, study, results, report}`, each `{state: empty|incomplete|ready|running|done, label}`, computed from the other tables, never stored. Only the owner or an admin may read or change a project.

Export zip: `project.json` (`{format: 1, name, exported}`) and `plant/<number>.json` (`{number, note, created, content}`, `content` is gemini's plant document), one file per plant version, plus `case/<number>.json` and `case/files/<number>/<name>` for the case versions and their files. Import takes the same zip.

#### workspace/overview

`GET /workspace/overview?project=` → `{progress, chats: [chat] (latest 5), activity: [activity] (latest 10), active_runs: [run]}`; `activity = {id, time, actor: {kind: user|agent, name}, text, link: {route, id}|null}`. Activity rows are written by the services that change things (case saved, plant saved, study started/finished, report exported, run finished).

#### workspace/rag (a project's Library, and the shared Knowledge)

| Method | Path | Body → Response |
|---|---|---|
| GET | `/workspace/rag?project={id}&cursor=` | → `{items: [rag_document], next}`; without `project`, the shared Knowledge documents |
| POST | `/workspace/rag` | multipart `project?`, `file` → `201 rag_document`; without `project` it adds a shared Knowledge document, which only an admin may (`403 forbidden` otherwise) |
| GET | `/workspace/rag/{id}/file` | → the file's bytes, shown inline (`Content-Disposition: inline`): a PDF as `application/pdf`, every text format as `text/plain; charset=utf-8` so markup never runs; `nosniff` and `Content-Security-Policy: sandbox` |
| GET | `/workspace/rag/{id}/text` | → `{id, name, searchable, text}`: the text the backend read, as the agents search it (`null` until read, or when it could not be) |
| DELETE | `/workspace/rag/{id}` | → `204`; a shared one only by an admin |

`rag_document = {id, project, name, size, searchable: pending|ready|failed, created}`; `project` is `null` for a shared Knowledge document. Text extraction and indexing run in a Celery task; a PDF's text keeps a `[page n]` line before each page. A project's documents feed `Workspace.rag`, `files` and `file`; the shared Knowledge feeds `Workspace.knowledge_search`, `knowledge_files` and `knowledge_file` (RAG: passages with their document and page). `python -m scripts.knowledge add <file> --by <admin email>` adds or replaces a shared document from the server, such as the cost catalogue.

### workspace/mcp

MCP servers the agents may use (shown to people as Connectors). Everyone signed in reads; only an admin writes. A project lists the ones its runs use in `project.mcp`; a disabled server is never given to a run.

| Method | Path | Body → Response |
|---|---|---|
| GET | `/workspace/mcp` | → list of `mcp_server`, by name |
| POST | `/workspace/mcp` | `{name, url, transport?: "http"\|"sse", auth?: "none"\|"bearer"\|"header", header_name?, secret?}` → `201 mcp_server`, checked once; `name` matches `[a-z0-9_-]{1,32}` (it names the tools, `<name>__<tool>`) and is unique; `bearer` needs `secret`, `header` needs `header_name` and `secret` |
| PATCH | `/workspace/mcp/{id}` | any of the create fields and `enabled` → `mcp_server`; a change to how it is reached clears the check (`status: "unchecked"`, no tools) |
| POST | `/workspace/mcp/{id}/check` | → `mcp_server` with what the server said now |
| DELETE | `/workspace/mcp/{id}` | → `204` |

`mcp_server = {id, name, url, transport, auth, header_name, has_secret, enabled, status: "unchecked"|"ok"|"error", error, checked, tools: [{name, description, read_only}], created}`. The secret is never sent back. `error` is `"<code>: <message>"` with geomind's codes `unreachable`, `auth_refused` or `bad_response`; while geomind has no MCP client a check leaves `status: "unchecked"` with an explanation in `error`. In a run a tool that is not read-only asks for approval (`request` kind `approval`), and `tool.started`/`tool.finished` carry `connector`.

### plant

Codes: `plant_not_found`, `module_not_found`, `entry_not_found`, `plant_invalid`.

Shapes:

```text
version    = {number, note, author: {id, name}, created}
template   = {name, title, description, purpose}
palette    = {type, title, category, summary}            from gemini's module registry
flowsheet  = {project, version, spec, layout,
              modules: [{id, type, title, category}],
              connections: [{source: "<id>.<port>", target: "<id>.<port>", stream, kind}]}
             spec: gemini's plant document, stored and returned unchanged
             layout: node positions, UI only, saved without a new version
             category: the module's gemini category (icon, palette group, layout)
             stream: the stream type of the connection, from gemini (colour)
parameters = {module, type, schema, values, missing, history: [{valid_from, params}]}
             schema: JSON schema of the module's parameters, each property with "unit"
             values: effective at ?at= (or latest); missing: properties with no value
problem    = {path, message, code}
```

#### plant/flowsheet

| Method | Path | Body → Response |
|---|---|---|
| GET | `/plant/flowsheet/palette?category=` | → list of `palette` |
| GET | `/plant/flowsheet/ports` | → `[{type, inlets: [{port, kind}], outlets: [{port, kind}]}]` from gemini's module registry; `kind` is gemini's stream kind |
| GET | `/plant/flowsheet/templates` | → list of `template` |
| GET | `/plant/flowsheet?project={id}` | → `flowsheet` of the latest version; `404 plant_not_found` if none |
| POST | `/plant/flowsheet` | `{project, base, note, spec, layout?}` or `{project, base, note, template, parameters?}` → `201 flowsheet` |
| PUT | `/plant/flowsheet/layout` | `{project, base, layout}` → `flowsheet` (no new version) |
| POST | `/plant/flowsheet/validate` | `{spec, project?}` → `{problems: [problem], warnings: [problem]}`; `warnings` never refuse a plant (with gemini 0.6, for example a port out of its range) |
| GET | `/plant/flowsheet/suggest?project=&port=<path.port>&limit=` | → `{port, suggestions: [{port, match: "exact"\|"loose", exact: [field], loose: [field], closes_loop}]}`, best first, the ports of the project's latest plant that `port` may connect to; `501 not_implemented` before gemini 0.6, `422` for a port the plant lacks |
| GET | `/plant/flowsheet/versions?project={id}` | → list of `version`, newest first |
| GET | `/plant/flowsheet/versions/{number}?project={id}` | → `flowsheet` of that version |

#### plant/parameters

| Method | Path | Body → Response |
|---|---|---|
| GET | `/plant/parameters?project={id}&module={id}&at={time?}` | → `parameters` |
| POST | `/plant/parameters` | `{project, base, module, params, valid_from?, note}` → `201 version` |
| POST | `/plant/parameters/fill` | `{project, base, module, entry, valid_from?, note}` → `201 version` |

#### plant/bindings and plant/catalogue (kept, not built yet: operation loop, later)

`bindings = {module, type, bindable: {controls: [name], boundaries: [name], inlets: {port: [field]}, measured: [name], state: [name]}, bindings: {controls: {name: binding}, boundaries: {...}, inlets: {port: {field: binding}}, measured: {...}, state: {...}}}`, `binding = {column, unit}`, `entry = {id, kind, name, manufacturer, params, created, updated}`.

| Method | Path | Body → Response |
|---|---|---|
| GET | `/plant/bindings?project={id}&module={id}` | → `bindings` |
| POST | `/plant/bindings` | `{project, base, module, bindings, note}` → `201 version` |
| GET | `/plant/catalogue?kind={name?}` | → list of `entry` |
| POST | `/plant/catalogue` | admin, `{kind, name, manufacturer?, params}` → `201 entry` |
| PATCH | `/plant/catalogue/{id}` | admin, `{name?, manufacturer?, params?}` → `entry` |
| DELETE | `/plant/catalogue/{id}` | admin → `204` |

Rules for every save: `base` must equal the latest version number (`null` when there is none), else `409 conflict` with `{"latest": n}` in `details`; identical content is `409 conflict`; gemini validation failures are `422 plant_invalid` with `details.problems`.

### design/case

The problem: everything that is not the plant. `content` is gemini's case document, stored and returned unchanged.

`case = {project, version, content, files: [{name, size}], missing: [{path, message}], problems: [problem]}`; `missing` and `problems` come from gemini's validation, never from backend rules.

| Method | Path | Body → Response |
|---|---|---|
| GET | `/design/case?project={id}` | → `case`; `404 case_not_found` if none |
| GET | `/design/case/schema` | → gemini's JSON schema of a case (with units) |
| POST | `/design/case` | `{project, base, note, content}` → `201 case` (invalid structure is `422 case_invalid`; missing values are allowed and listed) |
| POST | `/design/case/validate` | `{content}` → `{missing, problems}` |
| POST | `/design/case/files` | multipart `project`, `base`, `name`, `file` → `201 case` (a new version that references the file, e.g. a demand CSV; gemini checks it) |
| GET | `/design/case/files/{name}?project=&version=` | → the file |
| GET | `/design/case/series?project={id}` | → `{series: [{name, unit, points: [[time, value]]}]}` (read through gemini) |
| GET | `/design/case/versions?project={id}` | → list of `version` |

### design/study

Heavy calculations run as Celery jobs; progress goes to Redis and the frontend polls `GET /design/study?project=` every 2 s while any study is queued or running (no SSE).

`study = {id, project, kind, name, settings, status: queued|running|done|failed|cancelled|blocked, progress: {done, total}, started_by: {kind: user|agent, name, run?}, case_version, plant_version, plant_pinned, result, error, missing, created, ended}`. A study whose inputs are missing is created with `status=blocked` and `missing` filled; it is started later with `POST /design/study/{id}/start`.

| Method | Path | Body → Response |
|---|---|---|
| GET | `/design/study/kinds` | → `[{kind, title, description, schema}]` from gemini's study API, plus `size` |
| GET | `/design/study?project={id}` | → list of `study` |
| POST | `/design/study` | `{project, kind, name, settings, plant_version?}` → `201 study` (queued); `422 validation_failed` with `details.plant_version` when the project has no such version |
| GET | `/design/study/{id}` | → `study` |
| POST | `/design/study/{id}/start` | → `study` (a blocked study after the case is completed) |
| POST | `/design/study/{id}/cancel` | → `study` |

### design/results

All values come from gemini's evaluate/report output, passed through.

| Method | Path | Body → Response |
|---|---|---|
| GET | `/design/results?project={id}` | → `[{id, name, study, case_version, plant_version, kpis: [{name, title, value, unit}], checks: {passed, failed, not_assessed}, created}]` |
| GET | `/design/results/{id}` | → the summary plus `capacities: [{name, title, value, unit}]`, `coverage: [{date, source: geothermal|backup|short}] | null` (null until gemini publishes it), `constraints: [{name, title, status: pass|fail|not_assessed, message}]`, `series: [...]` |
| GET | `/design/results/compare?project={id}&ids=a,b,c&x={kpi}&y={kpi}` | → `{items: [result summary], pareto: [result id]}` from gemini's compare |

### reporting/design

| Method | Path | Body → Response |
|---|---|---|
| GET | `/reporting/design/parts` | → `[{key, title}]`, the report sections in order with their titles (the one source of section titles) |
| POST | `/reporting/design/preview` | `{project, result, run?, include: [capacities, design, checks, costs, agentlog]}` → `{title, sections: [{key, title, markdown}]}` |
| POST | `/reporting/design/export` | same body plus `format: md|pdf` → the file (PDF from the same Markdown; costs show their source, missing ones say "missing") |

### assistant/chat

| Method | Path | Body → Response |
|---|---|---|
| GET | `/assistant/chat?project={id}` | → list of `chat` |
| POST | `/assistant/chat` | `{project, title?}` → `chat` |
| GET | `/assistant/chat/{id}/messages` | → list of `message` |
| POST | `/assistant/chat/{id}/messages` | `{content}` → `{message, run}` |
| PATCH | `/assistant/chat/{id}` | `{title}` → `chat` |
| DELETE | `/assistant/chat/{id}` | → `204`; `409 conflict` while a run of the chat is `queued`, `running` or `waiting` |
| GET | `/assistant/chat/{id}/state` | → `{version, state, suggestions}` (the problem state; `{"version": 0, "state": null}` before the first change; `suggestions` holds next steps while the chat has no messages, else `[]`) |
| GET | `/assistant/suggestions?project=&chat=` | → `{suggestions: [{label, message}]}`: geomind's next steps for a new chat (or one of the project's chats), from the whole project's state; no model is called; `[]` when geomind has none |

`chat = {id, project, title, created, last_run: {id, status}|null}`; `message = {id, chat, role, content, created, run?, suggestions?}`; `suggestions` (`[{label, message}]` or `null`) are the next steps geomind gave with an assistant answer: a click sends `message` as the user's next message, `role` is `user` or `assistant`. The user message carries its `run` from creation, so a page reloaded mid-run finds the stream; the assistant message is created when the run ends, with the same `run`. Messages are listed oldest first.

### assistant/runs

| Method | Path | Body → Response |
|---|---|---|
| GET | `/assistant/runs?project={id}&status=active?` | → list of `run`, newest first (`status=active`: queued, running or waiting) |
| GET | `/assistant/runs/{id}` | → `run` |
| GET | `/assistant/runs/{id}/events` | Server-Sent Events, see section 2 |
| WS | `/assistant/runs/{id}/stream` | The same events over a WebSocket, see section 2 |
| GET | `/assistant/runs/{id}/log` | → `runlog` |
| GET | `/assistant/runs/{id}/log/export?format=json\|md` | → the log as a file |
| POST | `/assistant/runs/{id}/answer` | `{request, answer}` → `run` (approve, deny, or reply to a question); a question with options also takes the user's own typed text, which geomind marks as typed; only the question at a run's step limit (`continue` or `stop`) takes nothing but its options (`422` otherwise) |
| POST | `/assistant/runs/{id}/cancel` | → `run` |

`run = {id, chat, project, status, loop, started, ended, usage, request, error}`, `status` is `queued`, `running`, `waiting`, `done`, `failed` or `cancelled`. `request` is the pending request (as in the `request` event) while `waiting`, else `null`; `error` is `{code, message}` when `failed`, else `null`. Answering a run that is not waiting is `409 run_not_waiting`. `usage = {input_tokens, output_tokens, cost}`.

`runlog = {run, steps: [{index, agent, parent, llm_calls: [...], tool_calls: [...]}]}`, with `llm_call = {model, messages, answer, input_tokens, output_tokens, cost, duration}` and `tool_call = {call_id, tool, input, output, duration, error?}`. `agent` is the dotted agent path (`coordinator.designer`); `parent` is the parent step of a delegated (nested) run, or `null`. geomind builds this object: `gd.runlog(events)`.

`GET /assistant/usage?project={id}` → `{runs, input_tokens, output_tokens, cost}` (totals for the runs page header).

## 2. Live run events (backend → frontend, SSE)

Over a WebSocket the client first sends `{"token": "<access token>", "after": <sequence or -1>}`; a browser cannot set headers, and a token in the URL would reach logs. The server then sends one text frame per event, `{"event": "<type>", "id": <sequence or null>, "data": {...}}`, or `{"event": "heartbeat"}` in a quiet interval, and closes with `1000` after the root run's `run.finished`. Other close codes: `4400` bad first message, `4401` token refused, `4404` no such run or not yours, `1011` the stream failed. Reconnect with `after` set to the last `id` seen. A client that cannot open a socket reads the SSE route instead. Answers and cancel stay `POST` routes.

Each event: `event: <type>`, `data: <json>`, `id: <sequence number>`. The stream replays from `Last-Event-ID` on reconnect (`sequence > Last-Event-ID`; sequence numbers can have gaps). Every `data` also carries `agent` (dotted path) and `parent` (parent run id or `null`); they are left out of the table.

| Type | Data |
|---|---|
| `run.started` | `{run, loop}` |
| `step.started` | `{index, model, context_window?}` (`context_window`: the tokens a model call may hold, a positive integer, from geomind's `GEOMIND_CONTEXT_WINDOW`; live and replayed; left out when unset) (`model`: the agent's primary model id, e.g. `deepseek/deepseek-v4.1-flash-1017`; if a fallback model answers, that model appears in the `retry` event and in `runlog` `llm_call.model`) |
| `text.delta` | `{index, text, buffered?}` (`buffered: true` on the one event a reconnect receives for a running step: it holds the step's text so far and replaces what the client has for that step, and has no `id`) |
| `tool.started` | `{index, call_id, tool, input}` |
| `tool.finished` | `{index, call_id, output_summary, duration, error?, problem?}` (`error` is geomind's cut text; `problem = {code, path, message, suggestions}` is there when a failed tool gave a code: `no_case`, `case_incomplete` with the missing paths in `suggestions`, `files_unavailable`, `not_text`, `budget`, `nested_stopped`, `context_exceeded`, `already_read`) |
| `step.finished` | `{index, usage, text}` (usage of this step; `text` is the step's full assistant text, `""` if none; a client replaces the step's streamed `text.delta` with it, so replay after a reload and the live view match) |
| `state.changed` | `{version, changes}`; see *Problem state changes* below (emitted from S2) |
| `request` | `{request, call_id?, kind, message, options?}`; `kind` is `approval` or `question`; `options` is `[{value, label}]` (a question with fixed choices; absent for free text and for approvals); the run is `waiting` |
| `usage` | `{input_tokens, output_tokens, cost}` (running totals) |
| `run.finished` | `{status, stop_reason, message?, suggestions?}` (`suggestions`: `[{label, message}]`, the next steps of the root run's answer) |
| `study.recorded` | `{run, index, call_id?, study, tool, method, designs, best?}` (sent once after a study tool stored the chat artifact `study/<name>`: `study` is that key, `tool` the study tool, `method` gemini's study method, `designs` the plants it ran over, `best` the reference of the design it recommends; the backend adds the study to the project's list) |

**Problem state changes.** `version` is the state version after the change (starts at 1, +1 per event). `changes` is a list of JSON Patch operations (RFC 6902 subset) on the problem state document:

```json
{"version": 4, "changes": [
  {"op": "add", "path": "/requirements/-", "value": {"id": "R3", "text": "Cover peak cooling", "metric": "cooling_coverage", "target": 1.0, "tolerance": 0.0, "status": "open"}},
  {"op": "replace", "path": "/assumptions/A1/confirmed", "value": true},
  {"op": "remove", "path": "/questions/Q2"}
]}
```

`op` is `add`, `replace` or `remove`; `path` is a JSON Pointer. Lists of items with an `id` (`requirements`, `assumptions`, `results`, `questions`) are addressed by id, not index; `-` appends. The document's top-level keys are `goal`, `requirements`, `assumptions`, `design`, `results`, `verification`, `questions` (shape in `../docs/geomind-design.md` section 3). A client that missed a version reloads the full state (route added with B2 if needed).

**Answers to options.** For a question with `options`, the answer is `{"text": ...}`: one of the listed values, or the user's own typed text, which geomind marks as typed for the model. Only the step-limit question (options exactly `continue` and `stop`, no call) takes nothing but its options; anything else there raises `RequestError` in geomind and gets `422 validation_failed` from the backend; an approval never has `options`; an item appended with `-` to an id-addressed list must carry an `id`; approvals keep `{"approved": true}` or `{"approved": false, "reason": ...}`.

These are the geomind callback events with `event.is_public` true, forwarded as they are: `event.type` and `event.data()` (JSON-safe). geomind also emits internal events (`llm.completed`, `tool.result`, `permission`, `retry`, `sandbox.provisioned`, `sandbox.closed`, `error`, `compaction`); the backend saves every event through `RunStore.save_event` but streams only public ones. The internal events are the run's source of truth, used for recovery and the full log. `Callback.on_event(engine, event)` receives every event, so a publisher needs one method. The backend adds no event types of its own.

## 3. geomind interfaces (backend ↔ geomind)

The agent package is `geomind`, imported as `import geomind as gd` (not `gm`, which is gemini). The product, domain and infrastructure are named Geomind; the GitHub organisation is `geomind-spe-geohackathon-2026`.

Version 2.6 (2026-11-02: `Workspace.case`, chat-scoped artifacts; 2.5: `step.finished.text`; 2.4: event storage rules below; 2.3: checkpoints removed, recovery and resume read `load_events` only; `load_events`, the `error` event and `on_event` added after geomind S1; `model` on `step.started`, `options` shape and `state.changed` shape for the frontend). The backend implements `RunStore` and `Workspace` and passes them in; geomind ships a file and a memory implementation of each, the `OpenRouter` provider (the backend may use it directly instead of its own `LLM`), and `FakeLLM` for tests. All of it exists after geomind S1, so the backend never waits for later geomind phases.

```python
class LLM(Protocol):
    async def complete(
        self, messages, tools, *, model, settings, on_text=None
    ) -> Completion: ...

    # Completion: text, tool_calls, usage (input_tokens, output_tokens, cost), model, raw
    # on_text(delta) streams text; settings = temperature, max_tokens


class RunStore(Protocol):
    def save_event(self, run_id, event): ...
    def load_history(self, chat_id) -> list[Message]: ...
    def save_state(self, chat_id, state): ...  # problem state across messages
    def load_state(self, chat_id): ...  # None when the chat has none
    def save_artifact(
        self, run_id, key, data
    ): ...  # large tool results (bytes or JSON)
    def load_artifact(self, run_id, key): ...
    def save_chat_artifact(
        self, chat_id, key, data
    ): ...  # chat-scoped: the next message of the chat reads them
    def load_chat_artifact(
        self, chat_id, key
    ): ...  # semantics as in geomind's RunStore docstrings
    def load_events(
        self, run_id
    ) -> list[Event]: ...  # in sequence order; recovery and replay


# RunStore and Workspace are sync; geomind calls them from a worker thread.


class Workspace(Protocol):
    def plant(self, project_id): ...  # the stored plant as a gemini plant
    def case(
        self, project_id
    ): ...  # -> (case dict, folder with its files); files written to a per-run temp folder
    def documents(
        self, project_id, query
    ): ...  # document search: [{id, title, text, score}]


class SandboxProvider(
    Protocol
):  # optional; geomind ships LocalSandbox and DockerSandbox
    async def provision(self, manifest) -> Sandbox: ...
```

**Storing events.** `save_event(run_id, event)` receives the event object; the store saves the full `event.to_dict()` (public and internal fields, e.g. `loop_state`) and `load_events` rebuilds each one with `gd.event_from_dict(data)`, in `sequence` order. Saving only `event.data()` (the public view) loses what recovery needs. Nested (delegated) runs share the root run's log: their events arrive with the root `run_id` and carry their own `agent` and `parent`; `load_events(root)` returns all of them. From S2, `text.delta` is not passed to `save_event` (the full text is in `llm.completed`); it is only forwarded to callbacks for the live stream, so SSE reconnect replays text from the backend's own short-lived Redis buffer of the running step's deltas.

Entry point used by the backend:

```python
import geomind as gd

run = gd.Run(
    message=content,
    chat=chat_id,
    project=project_id,
    history=store.load_history(chat_id),
    llm=llm,
    store=store,
    workspace=workspace,
    sandbox=gd.sandbox.DockerSandbox(),
    permissions=gd.Permissions(mode="ask"),
    callbacks=[publisher],
    hooks=[
        gd.hooks.TokenBudget(...),
        gd.hooks.RequireApproval(...),
        gd.hooks.Cancellation(is_cancelled),
    ],
)
result = run.start()  # or await run.astart(); RunResult: run_id, status, answer, request, usage, stop_reason

run = gd.Run.load(
    run_id,
    llm=llm,
    store=store,
    workspace=workspace,
    sandbox=...,
    permissions=...,
    callbacks=[publisher],
    hooks=[...],
)
result = run.resume(
    request_id, answer
)  # or await run.aresume(...); in another process; hooks and callbacks are passed again
result = run.resume()  # continue a run whose process died while running

run.cancel()  # same process; across processes use gd.hooks.Cancellation
```

`answer` is `{"approved": true}`, `{"approved": false, "reason": "..."}` or `{"text": "..."}` for a question. `status` values are those of `run` in section 1. A `Message` is `{role, content, tool_calls?, tool_call_id?}` with `role` `user`, `assistant`, `tool` or `system`; `load_history` returns only `user` and `assistant` messages.

The backend never chooses the loop or the agents; geomind's coordinator does.

**Chat-scoped artifacts** (decided 2026-11-02): the backend stores them next to `save_artifact` / `load_artifact` on the same `run_artifacts` table (it holds both `run_id` and `chat_id`), so a chat's second message reads the case files, designs and results of the first run. The methods are additive.

**Run errors.** When a run ends with `status="failed"`, the backend fills `run.error` from `RunResult`: `code` = `stop_reason` (`error`, `step_limit`, `denied`, ...) and `message` = `RunResult.message`. geomind itself does not produce `{code, message}`.
