# Build the Geomind app: frontend and backend

You are the **coordinator** of a large, parallel build. You plan, dispatch subagents, review their summaries and diffs, merge, and run the checks. You do not write feature code yourself and you do not read large files yourself: subagents do that and report short summaries. This keeps your context free for the whole build.

Goal: a complete, clean, working web app for designing geothermal heating and cooling plants with an AI assistant, built exactly on the user flow of the clickable mockup `../docs/ui-mockup.html`, with a FastAPI backend that serves every screen. When this prompt is done, a user can sign in, create or open a project, chat with the agents and read their full logs, fill in the problem, edit the plant, run studies, compare results and export a report.

This prompt is self-contained. Everything you need that is not in the repos is in this file and in `../docs/ui-mockup.html`.

---

## 0. Where things are

```
/Users/sahand/Desktop/geomind-spe-geohackathon-2026/
├── backend/          FastAPI          YOU BUILD HERE (branch main)
├── frontend/         React            YOU BUILD HERE (branch main; may not exist yet)
├── infrastructure/   docker compose   write only if it owns the compose file (check first)
├── gemini/           physics engine   READ ONLY
├── geomind/          agent package    READ ONLY
└── docs/             shared docs      ui-mockup.html, contracts.md, this prompt
```

Hard rules about the repos:

- **gemini and geomind are read only.** Never edit, commit, branch or push there. If you need something from them that does not exist, write it into the requests lists (section 9) and build around the gap; never copy or reimplement physics or agent logic in the backend.
- **backend and frontend:** work and commit on `main`, push `origin main` at the end. No feature branches on origin, no PRs. Temporary worktree branches are local only and are deleted after merging.
- **Parallel sessions:** other Claude sessions may be working on gemini or geomind at the same time; that is fine. Before you start, check `git status` and `git log -5` in backend and frontend and look for `.tmp/session.lock`. If a lock exists and is younger than 2 hours, stop and report. Otherwise write your own lock (time + "app-frontend-backend") and delete it at the end.
- **Commits you did not make:** if new commits arrive on backend or frontend `main` during the run, stop and report instead of rebasing over them.

## 1. Rules for all code (repeat them to every subagent)

Product rules (from the project owner, all "very important"):

1. **General, never competition-specific.** The hackathon inputs are one example. No hackathon numbers, names, temperatures, prices or limits in code, defaults, UI copy or migrations. They may appear only in test fixtures and mock data, clearly named as examples.
2. **No default values for engineering or economic inputs.** Not in the backend, not in the UI, not "sensible" ones. A missing value is shown as missing (warning colour, the word "missing", what it blocks) and the request that needs it fails with a clear error. Technical settings (page size, timeouts) may have defaults.
3. **gemini is the source of truth** for every physics name, unit, schema and check. The backend passes gemini's data through; the frontend draws it. If gemini names something, use gemini's name.
4. **I/O naming:** functions that read or write a format are named `from_<format>` / `to_<format>` in Python (`from_csv`, `to_json`, `from_dict`, `to_dict`) and `from<Format>` / `to<Format>` in TypeScript (`fromCsv`, `toJson`). No `load_x`, `parse_x`, `export_x`, `serialize` for these.
5. **Folder names:** one word, lower case, no underscores, the same names in backend and frontend (`assistant/chat`, `design/case`).
6. **English only** in code, UI, docs and commit messages.

Code quality (the top goal: few bugs, simple, readable, just enough code):

- Nesting at most 3 levels; functions about 40 lines at most; guard clauses instead of deep `if`s; full-word names; no clever one-liners.
- **No comments inside code.** Docstrings (Python) and a one-line JSDoc on exported TS functions and components only, plus tool directives (`# noqa`, `// eslint-disable-next-line` with a reason in the docstring). Add a test that enforces this in both repos (tokenize Python; scan TS with the TypeScript compiler API or a regex on `//` and `/* */` outside strings, allowing JSDoc `/** */` directly above an export).
- No dead code, no speculative options, no "for later" flags, no unused exports. Delete what you replace.
- Explicit errors with stable codes; never swallow exceptions.
- Every bug fix starts with a failing test.

Tests (two profiles):

- **development** (default, local, every step): only the tests of changed files and of everything that imports them, in parallel. Python: `pytest -n auto` on the affected test folders; TS: `vitest related --run <changed files>`. Budget under 300 s. No test over about 1 s. Never call the network or a real LLM in tests.
- **before each commit:** the full fast suite of that repo, in parallel.
- **release** (CI only): the slow and e2e tiers. Do not run slow tiers locally except the single e2e pass in section 7.
- Temporary files and reports go to `.tmp/` (git-ignored) at the repo root. `docs/` holds only lasting docs.

Docs: every step updates `AGENTS.md` ("Start here" section with the current state) and the repo's `docs/` in the same commit, so a fresh session can read the docs and know where things stand.

If something is missing, unclear or risky, stop that piece and say so in the report instead of guessing.

## 2. How you run this (coordinator pattern)

- Phase A runs **alone** and fast (reading and conventions). Phase B (foundations) runs as **two parallel subagents**, one per repo, because everything after depends on it. Phase C runs **up to eight parallel subagents**, each in its own git worktree on a temporary local branch, with **disjoint file ownership** listed in section 6. Phase D integrates.
- Subagents use a lighter model: `sonnet` for building, `haiku` for read-only searches and inventories. Never the main model for subagents.
- Each subagent writes its detailed notes to `.tmp/build/<task>.md` and returns a summary of at most 15 lines: what it built, files touched, tests run and their result, open problems, requests for gemini or geomind.
- You merge worktrees **in the order of section 6**, run the development tests after each merge, fix conflicts by re-dispatching the owning subagent (not by editing yourself), and remove the worktrees and temporary branches when merged.
- Contract first: no subagent changes a route or payload that is not in `../docs/contracts.md`. If one needs a change, it stops, describes it, and you update the contract (bump its version) and tell the affected subagents.

---

## 3. Phase A: read, learn, set conventions (before any code)

Dispatch these in parallel, read-only except where noted:

A1 (haiku) **Backend inventory** → `backend/.tmp/build/inventory-backend.md`: the tree, routes, models, migrations, settings, test layout and how tests run; what section 5.1 says exists, and any difference.

A2 (haiku) **gemini public API inventory** → `backend/.tmp/build/inventory-gemini.md`: only the public names (`import gemini as gm`, its `__all__`, its docs folder and AGENTS.md). Map each need in section 5.3 to a gemini name and signature, or mark it MISSING. Check the case (problem) API, plant spec API (validate, from spec, templates, module registry with categories and parameter schemas with units, stream types of ports), study API (kinds, settings schema, progress callback, cancellation), evaluate/report API (KPIs, constraint checks, daily coverage, compare/Pareto), units handling, error classes.

A3 (haiku) **geomind backend contract inventory** → `backend/.tmp/build/inventory-geomind.md`: from `geomind/.claude/docs/contracts.md` (section "For the backend"), `api.md`, `events.md`: `gd.Run` arguments, `RunStore` and `Workspace` protocols (including `Workspace.case`), event types and `event_from_dict`, `gd.runlog`, `FakeLLM` / testing helpers, providers, hooks (token budget, approval, cancellation). Note any difference from section 5.4.

A4 (haiku) **Mockup inventory** → `frontend/.tmp/build/inventory-mockup.md` (create the folder if the repo does not exist yet): every screen of `../docs/ui-mockup.html`, its route, its components, its data, every interaction, the design tokens (colours, stream colours, fonts, spacing, radii) and the user flow. Open it in a browser (Playwright) and take a screenshot of each screen into `.tmp/build/mockup/`.

A5 (sonnet) **Frontend best practices** → write `frontend/docs/conventions.md` (lasting doc). Read the current official sources first, then write short, concrete rules with small examples, specific to this stack:
- react.dev: "Thinking in React", "Keeping Components Pure", "You Might Not Need an Effect", "Rules of Hooks", "Choosing the State Structure", "Sharing State Between Components", "Reusing Logic with Custom Hooks".
- TypeScript strict mode handbook; typescript-eslint strict and stylistic configs.
- TanStack Query: query keys, query options factories, mutations and invalidation, optimistic updates, suspense vs status flags.
- React Router (data routers, nested layouts, loaders only where they help, protected routes).
- bulletproof-react (feature folders, no cross-feature imports, shared layer), and Testing Library guiding principles (test what the user sees; `getByRole`).
- Accessibility basics (labels, focus, keyboard, contrast), and form handling with react-hook-form plus a JSON-schema resolver (ajv).
End with a checklist that every frontend subagent must follow.

A6 (sonnet) **Backend best practices** → update `backend/docs/conventions.md` (merge with what exists, do not lose rules): FastAPI (dependencies, routers, response models, lifespan, background work in Celery, not in requests), Pydantic v2, SQLAlchemy 2.0 typed models and sessions, Alembic migration rules, Celery task idempotency and retries, SSE with Redis pub/sub, structured errors, and the zhanymkanov "fastapi-best-practices" list where it fits this repo's existing layout. End with a checklist.

A7 (sonnet) **Contract update** → edit `../docs/contracts.md` (the shared contract file): add everything in section 5.2 marked NEW, bump the file version and add a one-line changelog entry at the top. If `../docs/contracts.md` is missing or older than version 18, write it from section 5 of this prompt instead.

When all of A1–A7 are back, read only their summaries, then write `.tmp/build/plan.md` in backend: the final list of Phase C tasks with owners and the gemini/geomind gaps found. If A2 shows that a whole design feature has no gemini API at all, keep its routes, return `501 not_implemented` with the missing gemini name in `details`, put it in the requests list, and build the frontend for it against the mock.

## 4. Phase B: foundations (two parallel subagents)

B-F (sonnet) **Frontend foundation**, in `frontend/`:

1. If the repo does not exist: `git init -b main`. If no `origin`, create a private GitHub repo `geomind-spe-geohackathon-2026/frontend` with `gh repo create --private --source . --remote origin` (ask the user in the session before creating it).
2. Stack: Vite, React 18, TypeScript strict, Tailwind, shadcn/ui (Radix) copied into `src/shared/ui/`, React Router, TanStack Query, react-hook-form + ajv, `@microsoft/fetch-event-source` for SSE (the browser `EventSource` cannot send the bearer header), `@xyflow/react` + `elkjs` for the flowsheet, a small chart layer (Recharts or hand-written SVG components; choose one and say why in `docs/`), `lucide-react` icons, MSW for the mock API, Vitest + Testing Library, Playwright for e2e. Fonts IBM Plex Sans and IBM Plex Mono, self-hosted (no CDN). ESLint (typescript-eslint strict), Prettier, `npm run check` = types + lint + tests.
3. Layout:
   ```
   src/
   ├── app/          router, layouts (signin, home, project), providers, auth guard, error boundary
   ├── domains/<domain>/<feature>/   pages, components, api.ts (query options + mutations), hooks, tests
   ├── shared/       ui, api (client, errors, types), sse, forms, charts, quantity, layout
   ├── mocks/        MSW handlers, one file per domain, plus fixtures
   └── lib/
   ```
   Domains and features: `identity/{authn,me,users}`, `workspace/{projects,overview,documents,settings}`, `assistant/{chat,runs}`, `design/{case,plant,study,results,report}`. Features never import each other; shared code goes to `shared/`.
4. **Design tokens from the mockup**: role-named CSS variables (background, surface, sunken, border, text, muted, accent, ok, warn, bad, and stream tokens hot/heat/cold/power/gas), light and dark themes, system default plus a toggle; compact engineering density; tabular numbers. One `Quantity` component renders value + unit everywhere; one `Missing` component renders a missing value and what it blocks.
5. **Three-level shell exactly as the mockup**: `/signin` (no chrome); `/projects`, `/account`, `/users` (top bar only); `/projects/:projectId/...` (top bar with breadcrumb, active-run pill and user menu, plus the project sidebar). The sidebar appears only inside a project. Unknown project → back to `/projects` with a message. Routes inside a project: `overview`, `assistant/chat/:chatId?`, `assistant/runs`, `assistant/runs/:runId`, `design/case`, `design/plant`, `design/study`, `design/results/:resultId?`, `design/report`, `documents`, `settings`. Operation entries are visible and disabled with a "later" tag.
6. **API client**: one typed client for `/api/v1` with bearer token, single-flight refresh on 401 (refresh tokens rotate: keep the new one), the contract error shape mapped to a typed `ApiError`, `?cursor=` pagination helper. TypeScript types are generated from the backend's OpenAPI with `openapi-typescript` (`npm run gen:api` reads `../backend/openapi.json`, which the backend writes with a script); MSW handlers use the same types, so mock and real cannot drift.
7. `VITE_API_MODE=mock|real`, mock by default in development; the mock keeps state in memory for the session (create a project, it is there until reload).
8. Tests: shell routing, auth guard, refresh flow, the no-comments test.

B-B (sonnet) **Backend foundation**, in `backend/`:

1. Read `docs/conventions.md` (after A6) and the inventory. Keep the existing layout: `src/api/v1/<domain>/<feature>/{router,schemas,services,tasks}.py`, models and repositories in `src/core/clients/postgres/`, Redis in `src/core/clients/redis/`, `src/core/gemini/` is the **only** place that imports gemini, `src/api/v1/assistant/runs/adapters/` is the **only** place that imports geomind. Extend the import boundary test for both.
2. **All new tables and migrations in one go** (one owner avoids Alembic conflicts): `case_versions` (project, number, note, author, content JSON as gemini writes it, created) and `case_files` (project, version, name, size, object key in MinIO); `chats`, `messages`, `runs` (with usage totals, status, request, error, loop), `run_events` (run, sequence, type, public flag, data JSON = full `event.to_dict()`), `run_artifacts` (**both** `run_id` and `chat_id`, key, bytes or JSON, created; indexed on `(run_id, key)` and `(chat_id, key, created)`; see section 5.4), `chat_states` (chat, version, state JSON); `studies` (project, kind, settings JSON, status, progress done/total, started_by kind+name+run?, case_version, plant_version, result id, error, timestamps); `results` (project, study, name, case_version, plant_version, summary JSON, content JSON from gemini); `documents` (project, name, size, object key, searchable status); `activity` (project, time, actor kind+name, text, link). Indexes for every list route.
3. New error code `not_implemented` (501) with `details = {"missing": "<gemini or geomind name>"}`; update the error docs and tests.
4. A script `scripts/to_openapi.py` that writes `openapi.json` at the repo root (committed), and a test that fails when it is stale.
5. Celery: the base task, progress reporting through Redis, cancellation flag in Redis, and `tasks.py` naming as in the repo.
6. SSE helper: subscribe to Redis first, then replay stored events after `Last-Event-ID`, then stream live; heartbeat comments; works with `fetch` + bearer.

Merge B-F and B-B before Phase C.

## 5. What to build

### 5.1 Backend today (already built, keep and extend)

Last pushed 2026-10-30, about 130 fast tests: login, refresh (rotating), logout; `GET /identity/me`, password change (revokes every token); admin users list, create, patch role/name/active (users are never deleted; no public sign up, no forgot-password route); projects list, create, get, delete, export zip, import zip (owner or admin only; a project you may not see is `404 project_not_found`); health; contract error bodies; cursor pagination; rate limiting; `plant_versions` table (no plant routes yet; `src/core/gemini/plant.py` still uses the old `plant_type` class-path format and must move to gemini's JSON plant spec, format 2); clients for Postgres, Redis, OpenRouter, MinIO, InfluxDB, ChromaDB; Celery app; Docker image with FastAPI, Celery and Traefik.

### 5.2 HTTP API (all under `/api/v1`; JSON; UTC ISO times)

Shared rules: bearer auth; errors `{"error": {"code", "message", "details"}}`; lists `{"items": [...], "next": cursor|null}` with `?cursor=` and `?limit=`; every create answers `201`; stable codes `unauthorized` 401, `forbidden` 403, `not_found` / `<thing>_not_found` 404, `validation_failed` 422 (`details.fields`), `conflict` 409, `run_not_waiting` 409, `plant_invalid` 422 (`details.problems`), `case_invalid` 422 (`details.problems`) NEW, `missing_inputs` 422 (`details.missing = [{path, message}]`) NEW, `rate_limited` 429, `unavailable` 503, `not_implemented` 501 NEW, `internal` 500. Every save of a versioned thing takes `base` (the latest version number, or `null`) and answers `409 conflict` with `details.latest` when it is stale; identical content is `409 conflict`.

**identity** (exists): `POST /identity/authn/login|refresh|logout`, `GET /identity/me`, `POST /identity/me/password`, `GET|POST /identity/users`, `PATCH /identity/users/{id}`. `user = {id, email, name, role: admin|member, active}`.

**workspace/projects** (exists, extend):
- `GET /workspace/projects?search=` NEW filter; `POST`; `GET /{id}`; `PATCH /{id}` `{name}` NEW; `DELETE /{id}`; `GET /{id}/export`; `POST /import`.
- `project = {id, name, owner: {id, name}, plant_version, case_version, created, updated, progress}` with `progress = {case, plant, study, results, report}`, each `{state: empty|incomplete|ready|running|done, label}` (for the cards and the overview stepper; computed in the service from the other tables, never stored). NEW fields.
- Export zip adds `case/<number>.json` and `case/files/<number>/<name>`; import reads them.

**workspace/overview** NEW: `GET /workspace/overview?project=` → `{progress, chats: [chat] (latest 5), activity: [activity] (latest 10), active_runs: [run]}`; `activity = {id, time, actor: {kind: user|agent, name}, text, link: {route, id}|null}`. Activity rows are written by the services that change things (case saved, plant saved, study started/finished, report exported, run finished).

**workspace/documents** NEW: `GET /workspace/documents?project=`, `POST /workspace/documents` (multipart `project`, `file`) → `201 document`, `DELETE /workspace/documents/{id}`; `document = {id, project, name, size, searchable: pending|ready|failed, created}`. Files in MinIO; text extraction and indexing in a Celery task; search for the assistant's `Workspace.documents` (keyword search is enough now; ChromaDB only if it is already wired and simple).

**plant** (contract version 18, build now on gemini's spec format 2):
- `GET /plant/flowsheet/palette?category=` → `[{type, title, category, summary}]` from gemini's module registry.
- `GET /plant/flowsheet/templates` → `[{name, title, description, purpose}]`.
- `GET /plant/flowsheet?project=` → `flowsheet = {project, version, spec, layout, modules: [{id, type, title, category}], connections: [{source: "id.port", target, stream, kind}]}`; `404 plant_not_found` if none.
- `POST /plant/flowsheet` `{project, base, note, spec, layout?}` or `{project, base, note, template, parameters?}` → `201 flowsheet`.
- `PUT /plant/flowsheet/layout` `{project, base, layout}` → `flowsheet` (no new version).
- `POST /plant/flowsheet/validate` `{spec}` → `{problems: [{path, message, code}]}`.
- `GET /plant/flowsheet/versions?project=`, `GET /plant/flowsheet/versions/{number}?project=`; `version = {number, note, author: {id, name}, created}`.
- `GET /plant/parameters?project=&module=&at=` → `{module, type, schema, values, history}` (schema = gemini's JSON schema with `unit` on each property; a property with no value is listed in `missing`); `POST /plant/parameters` `{project, base, module, params, valid_from?, note}` → `201 version`.
- Bindings and catalogue routes stay in the contract but are **not** built in this prompt (operation loop, later).

**design/case** NEW (the problem: everything that is not the plant; content is gemini's case document, stored and returned unchanged):
- `GET /design/case?project=` → `case = {project, version, content, files: [{name, size}], missing: [{path, message}], problems: [{path, message, code}]}`; `404 case_not_found` if none. `missing` and `problems` come from gemini's validation, never from backend rules.
- `GET /design/case/schema` → gemini's JSON schema of a case (with units), for the forms.
- `POST /design/case` `{project, base, note, content}` → `201 case` (new version; invalid structure is `422 case_invalid`; missing values are allowed and listed).
- `POST /design/case/validate` `{content}` → `{missing, problems}`.
- `POST /design/case/files` multipart `project`, `base`, `name`, `file` → `201 case` (a new version that references the file, e.g. a demand CSV; the file is checked by gemini).
- `GET /design/case/files/{name}?project=&version=` → the file; `GET /design/case/series?project=` → `{series: [{name, unit, points: [[time, value]]}]}` for the demand charts, read through gemini.
- `GET /design/case/versions?project=`.

**design/study** NEW (heavy calculations as Celery jobs):
- `GET /design/study/kinds` → `[{kind, title, description, schema}]` from gemini's study API (size, optimise, uncertainty, sensitivity, ... whatever gemini publishes).
- `GET /design/study?project=` → list of `study`; `POST /design/study` `{project, kind, name, settings}` → `201 study` (queued); `GET /design/study/{id}`; `POST /design/study/{id}/cancel` → `study`.
- `study = {id, project, kind, name, settings, status: queued|running|done|failed|cancelled|blocked, progress: {done, total}, started_by: {kind: user|agent, name, run?}, case_version, plant_version, result, error, missing, created, ended}`. A study whose inputs are missing is created with `status=blocked` and `missing` filled (it can be started again later with `POST /design/study/{id}/start` NEW after the case is completed).
- Progress is pushed to Redis; the frontend polls `GET /design/study?project=` every 2 s while any study is queued or running (no SSE needed).

**design/results** NEW:
- `GET /design/results?project=` → `[{id, name, study, case_version, plant_version, kpis: [{name, title, value, unit}], checks: {passed, failed, not_assessed}, created}]`.
- `GET /design/results/{id}` → `{..., capacities: [{name, title, value, unit}], coverage: [{date, source: geothermal|backup|short}], constraints: [{name, title, status: pass|fail|not_assessed, message}], series: [...]}`, all from gemini's evaluate/report output, passed through.
- `GET /design/results/compare?project=&ids=a,b,c&x=<kpi>&y=<kpi>` → `{items: [result summary], pareto: [result id]}` from gemini's compare.

**reporting/design** NEW:
- `POST /reporting/design/preview` `{project, result, run?, include: [capacities, design, checks, costs, agentlog]}` → `{title, sections: [{key, title, markdown}]}`.
- `POST /reporting/design/export` same body + `format: md|pdf` → the file. PDF from the same Markdown with one small, well-known library (say which and why in `docs/`). Costs show their source next to each number; missing ones say "missing".

**assistant/chat** and **assistant/runs** (contract version 18; build now):
- `GET /assistant/chat?project=`, `POST /assistant/chat` `{project, title?}`, `GET /assistant/chat/{id}/messages`, `POST /assistant/chat/{id}/messages` `{content}` → `201 {message, run}`, `PATCH /assistant/chat/{id}` `{title}`, `DELETE /assistant/chat/{id}` (409 while a run of the chat is queued/running/waiting), `GET /assistant/chat/{id}/state` → `{version, state}`.
- `GET /assistant/runs?project=&status=active?`, `GET /assistant/runs/{id}`, `GET /assistant/runs/{id}/events` (SSE), `GET /assistant/runs/{id}/log` → `gd.runlog(events)`, `GET /assistant/runs/{id}/log/export?format=json|md` NEW, `POST /assistant/runs/{id}/answer` `{request, answer}`, `POST /assistant/runs/{id}/cancel`.
- `chat = {id, project, title, created, last_run: {id, status}|null}`; `message = {id, chat, role: user|assistant, content, created, run?}` (the user message carries its run from creation; the assistant message is written when the run ends); `run = {id, chat, project, status: queued|running|waiting|done|failed|cancelled, loop, started, ended, usage: {input_tokens, output_tokens, cost}, request, error: {code, message}|null}`.
- `GET /assistant/usage?project=` NEW → `{runs, input_tokens, output_tokens, cost}` for the runs page header.

**SSE events** (backend → frontend), each `event: <type>`, `data: <json>`, `id: <sequence>`; every data carries `agent` (dotted path) and `parent`: `run.started {run, loop}`, `step.started {index, model}`, `text.delta {index, text}`, `tool.started {index, call_id, tool, input}`, `tool.finished {index, call_id, output_summary, duration, error?}`, `step.finished {index, usage, text}` (replaces the streamed text of that step), `state.changed {version, changes}` (JSON Patch subset add/replace/remove; id-addressed lists), `request {request, call_id?, kind: approval|question, message, options?: [{value, label}]}`, `usage {input_tokens, output_tokens, cost}`, `run.finished {status, stop_reason, message?}`. Sequence numbers can have gaps; replay uses `sequence > Last-Event-ID`. `text.delta` is not stored by geomind: keep a short-lived Redis buffer of the running step's deltas for reconnects.

### 5.3 What the backend needs from gemini (all through `src/core/gemini/`)

Case: from/to dict, JSON schema with units, validate → missing + problems, read the files a case names (series for charts). Plant: spec validate → problems with paths, build from spec, templates, module registry (type, title, category, summary, parameter schema with units), port stream types, migration of older plant formats. Study: list of kinds with settings schemas, run with a progress callback and a cancel check, result object. Evaluate: KPIs with units, capacities, daily coverage by source, constraint checks with pass/fail/not assessed, compare with a Pareto set. Errors: gemini's error classes mapped to `case_invalid`, `plant_invalid`, `missing_inputs`. Each function in `src/core/gemini/` is small, typed, has a docstring and a test; every gemini call is wrapped once, in one file per area (`case.py`, `plant.py`, `study.py`, `evaluate.py`). Anything missing → requests list.

### 5.4 What the backend needs from geomind (all through `assistant/runs/adapters/`)

```python
import geomind as gd
run = gd.Run(message=content, chat=chat_id, project=project_id,
             history=store.load_history(chat_id),
             llm=llm, store=store, workspace=workspace,
             sandbox=..., permissions=gd.Permissions(mode="ask"),
             callbacks=[publisher], hooks=[token budget, approval, cancellation])
result = run.start()                       # RunResult: run_id, status, answer, request, usage, stop_reason, message
run = gd.Run.load(run_id, llm=..., store=..., workspace=..., callbacks=[...], hooks=[...])
result = run.resume(request_id, answer)    # answer: {"approved": true} | {"approved": false, "reason"} | {"text"}
```

- `RunStore` (sync, called from a worker thread): `save_event(run_id, event)` stores the full `event.to_dict()` (never only `event.data()`); `load_events(run_id)` rebuilds with `gd.event_from_dict` in sequence order; `load_history(chat_id)` returns user and assistant messages; `save_state` / `load_state` store the dict as given (it may hold a `compaction` key that is never shown or patched); `save_artifact` / `load_artifact` (per run) and `save_chat_artifact` / `load_chat_artifact` (per chat). Delegated runs write into the root run's log with their own `agent` and `parent`.
- `Workspace`: `plant(project_id)` (latest plant as a gemini plant), `case(project_id)` → `(case dict, folder with its files)` (write the case files to a per-run temp folder), `documents(project_id, query)` → `[{id, title, text, score}]`.
- `LLM`: geomind's `OpenRouter` provider with the backend's settings; tests use geomind's `FakeLLM` / testing helpers only.
- Hooks: token budget per project from settings; approval for heavy tools (geomind decides which); cancellation reads the Redis flag.
- The backend never chooses the loop or the agent and never passes `agent=`.
- **Artifacts are chat-scoped (decided by the project owner, 2026-11-02).** geomind's `RunStore` protocol gains two methods: `save_chat_artifact(chat_id, key, data)` and `load_chat_artifact(chat_id, key)`; follow the exact semantics in geomind's `RunStore` docstrings (A3 records them), so the second message of a chat can read the case files, designs and results the first run produced. Implement them next to `save_artifact` / `load_artifact` on the same `run_artifacts` table (it stores both `run_id` and `chat_id`). Check A3's inventory: if the geomind on disk does not have these methods yet, implement them anyway (they are additive), test them directly, and list "geomind: chat-scoped artifact methods not released yet" in the report.
- `run.error` = `{code: stop_reason, message: RunResult.message}` when failed.
- Studies started by an agent: if geomind's study tools run gemini directly, the backend does not see them as `studies` rows. Do not fake them; list in the geomind requests that the backend wants a hook or event to record agent studies and results, and show agent results that arrive as artifacts only if geomind exposes them clearly.

### 5.5 Frontend screens (follow the mockup; it is the spec for flow and layout, not for numbers)

Every screen has loading, empty, error and permission states; every number comes from the API with its unit; nothing is hard-coded except UI copy.

- **Sign in** (`identity/authn`): email, password, error message on 401, "ask an admin" note, redirect to where the user was going.
- **Projects home** (`workspace/projects`): cards with name, owner, updated, progress bar (5 segments from `progress`), counts; search; "New project" dialog (name; start from an empty problem, a copy of another project's problem, or a project zip); import zip.
- **User menu**: account, users (admins only), theme (system/light/dark, remembered), sign out.
- **Account** (`identity/me`): profile, change password (then sign out everywhere, as the backend does).
- **Users** (`identity/users`, admin): list, add, change role, deactivate/activate.
- **Overview** (`workspace/overview`): project title, "Ask the assistant" box (creates a chat with the first message and opens it), the five-step stepper (Problem, Plant, Study, Results, Report) with state chips that open each page, recent chats, activity feed.
- **Chat** (`assistant/chat`): three columns (chat list with new/rename/delete; conversation; run panel). A message is a list of blocks in event order: Markdown text (no raw HTML), tool cards (one line; expand for input and output summary; errors in red), delegated agent groups nested by `parent` (two levels indented, deeper ones flattened with the dotted path), request cards (approval with Approve/Deny and optional reason; question with option buttons or free text) inline and sticky above the input while waiting. Input with Send; Cancel while active. Run panel: status and timer, running tokens and cost, agent tree, "what it knows" (the problem state from `state.changed`, applied as JSON Patch; reload full state on a version gap), link to the full log. The live view is one pure reducer `applyEvent(view, event)`; after a reload it replays from event 0 and must match the live view exactly (unit-test this with a recorded event list).
- **Runs** (`assistant/runs`): table with run, chat, agents, status, tokens, cost, started; project totals in the header; row opens the log.
- **Run log** (`assistant/runs/:runId`): header with totals and Export JSON / Markdown; left step tree by agent; right the selected step: LLM call (system prompt and history collapsed; new messages and answer open; model, tokens, cost, duration), tool calls with formatted input and output; footer table per agent and per model. Must read well on a screen recording.
- **1 Problem** (`design/case`): a blocker banner listing missing values and what they block, with a link to the field; tabs built from gemini's case schema sections (the mockup shows Demand, Site and reservoir, Constraints, Economics; use whatever sections the schema has, never a hard-coded list); forms generated from the JSON schema with units (react-hook-form + ajv), missing fields marked; file upload/replace for series files with a chart of each series; validate as you type (debounced `validate`), save as a new version with a note; version history.
- **2 Plant** (`design/plant`): flowsheet editor on the spec: palette from the API grouped by category; drag to add (generated, editable id); connect ports (port colour = stream token; refuse mismatched streams on the canvas, backend stays the authority); live validation with problems shown on the module/connection and in a list; Save version (disabled while invalid; 409 → reload prompt); discard; unsaved-changes guard; start from a template; ELK auto layout when no layout, user positions saved with `PUT layout` (debounced); right panel: parameter form from the module schema with units and missing marks; History tab with restore.
- **3 Study** (`design/study`): table of studies with kind, started by (user or agent), progress bar, status, result link or "missing X" link; "New study" dialog: pick a kind, settings form from its schema; blocked studies show what is missing and a Start button once fixed; cancel.
- **4 Results** (`design/results`): a tab per result plus Compare; KPI tiles; days-covered strip (one cell per day, coloured by source, with a legend); constraint table; Compare: scatter of two chosen KPIs with the Pareto line and a table; "Make report from this result".
- **Report** (`design/report`): pick result and run, choose sections, live preview from `preview`, export PDF and Markdown.
- **Documents** (`workspace/documents`): upload, list with searchable status, delete.
- **Project settings** (`workspace/settings`): rename, export zip, delete with an in-page confirmation (never `window.confirm`).
- **Top bar**: breadcrumb (Projects / project / section / page), active-run pill (opens the running chat), avatar menu. Toasts for completed actions ("Plant v8 saved").

MSW mocks: realistic, contract-typed fixtures for every route, a scripted SSE run that plays a full design conversation including a delegated agent, an approval request and a cancel, a study that progresses, and a project with a missing value. Fixtures are clearly example data.

## 6. Phase C: parallel build (worktrees, disjoint ownership, merge in this order)

| # | Owner | Repo | Owns (only these paths) |
|---|---|---|---|
| C1 | sonnet | backend | `src/api/v1/workspace/**` (projects extensions, overview, documents), activity writer service in `src/core/activity/`, their tests |
| C2 | sonnet | backend | `src/core/gemini/{case,plant,errors}.py`, `src/api/v1/plant/**`, `src/api/v1/design/case/**`, their tests |
| C3 | sonnet | backend | `src/core/gemini/{study,evaluate}.py`, `src/api/v1/design/{study,results}/**`, `src/api/v1/reporting/**`, their tests |
| C4 | sonnet | backend | `src/api/v1/assistant/**` incl. `runs/adapters/`, SSE wiring, their tests |
| C5 | sonnet | frontend | `src/domains/{identity,workspace}/**`, `src/mocks/{identity,workspace}.ts` |
| C6 | sonnet | frontend | `src/domains/assistant/**`, `src/shared/sse/**`, `src/mocks/assistant.ts` |
| C7 | sonnet | frontend | `src/domains/design/{case,plant}/**`, `src/shared/forms/**`, `src/mocks/{case,plant}.ts` |
| C8 | sonnet | frontend | `src/domains/design/{study,results,report}/**`, `src/shared/charts/**`, `src/mocks/{study,results,report}.ts` |

Shared files (router registration, `src/api/v1/router.py`, `src/app/router.tsx`, `openapi.json`, docs index): subagents do not edit them; each lists the lines it needs in its summary and you apply them in one small commit after merging (this is the only code you write yourself). Each subagent: reads `docs/conventions.md` and its inventory notes first, works test-first, runs development tests, commits in small steps on its temporary branch, updates the docs of its area, returns its summary. A backend subagent that hits a gemini or geomind gap writes it to its `.tmp/build/<task>.md` under "Requests" and returns `501 not_implemented` for that route.

## 7. Phase D: integrate and verify

1. Regenerate `openapi.json`, then `npm run gen:api` in frontend; fix type errors by re-dispatching owners.
2. Run the backend locally (docker compose for Postgres/Redis/MinIO, or the test settings), seed one admin and one example project from fixtures, set `VITE_API_MODE=real`, and run **one** Playwright pass of the golden path: sign in → create project → overview → open chat, send a message (backend uses geomind's `FakeLLM` scripted run in this mode; never a real LLM in tests) → approve the request → open the run log → problem page shows a missing value → fill it → plant page validates → start a study → results → report preview → sign out. Also run the same pass in mock mode. Save screenshots of every screen to `frontend/.tmp/build/screens/` and compare them with the mockup screenshots from A4; list visible differences in the report.
3. Full fast suites in both repos, lint, types, the no-comments tests, the import boundary tests.
4. Merge the two requests lists (section 9) into `backend/.tmp/build/requests.md` and copy the final text into the report.

## 8. Docs and finish

- backend: `AGENTS.md` Start here, `docs/` (architecture, routes per domain, gemini and geomind adapters, errors, Celery and SSE, testing), `README.md` run instructions.
- frontend: `AGENTS.md`, `docs/` (conventions, architecture and folders, design tokens, data fetching, SSE and the event reducer, forms from schemas, mocks, testing), `README.md`.
- `../docs/contracts.md` updated and versioned.
- Commit per step with clear messages; push `origin main` in backend and frontend; remove worktrees, temporary branches and your lock.

## 9. Requests lists (what we should build in gemini or geomind)

Collect, do not implement. Two lists, `gemini` and `geomind`, each item:

```
- [gemini|geomind] <short title>
  Needed by: <route or screen>
  Today: <what exists, with the public name, or "nothing">
  Wanted: <the public function/field/event, its signature and return shape>
  Blocking: yes (route returns 501) | no (worked around: how)
```

Typical candidates to check (do not assume; verify in the inventories): case JSON schema with units and section titles; validate returning missing vs structural problems separately; a progress callback and cancellation in study functions; daily coverage by source in the evaluate report; compare with Pareto ids; stream type per port; module titles and summaries for the palette; a geomind event or hook when an agent runs a study or produces a result, so the backend can show it in Study and Results.

## 10. Report back (in the session, at the end)

1. What was built, per repo, with the commit range pushed.
2. Test counts and durations (development and full fast suites), e2e result, lint and types.
3. Every route that returns `501 not_implemented` and why.
4. The requests lists, ready to paste.
5. Differences from the mockup, and any contract change made (new version number).
6. Anything risky, unclear or left undone.

