# Handover: Phase D of the app build

Read this first, then `app-frontend-backend.md` sections 1 and 7 to 10. Phases A, B, C and the integration pass (D3) are done; see Phase D status.

In a new clone the prompt's `../docs/` paths do not exist, because `docs/` was never a git repo. Their files are here: `contracts.md` (version 20, wins over the prompt), `ui-mockup.html`, `app-frontend-backend.md`, `plan.md` (gap decisions), `requests.md` (ready to paste), `inventories/`.

## New machine

Tools: Python 3.12, Node 22 with npm, Docker with compose, git over SSH with access to the repos below.

Folder layout (siblings, because `requirements.txt` and compose use relative paths):

```
geomind-spe-geohackathon-2026/
├── backend/          git@github.com:SahandNZ/backend.git
├── frontend/         git@github.com:geomind-spe-geohackathon-2026/frontend.git
├── gemini/           git@github.com:geomind-spe-geohackathon-2026/gemini.git   branch dev, 0.5.0 or newer (b07b7ff)
├── geomind/          git@github.com:crust-team/geomind.git                     branch main, read section "geomind" below
├── infrastructure/   git@github.com:swarmax/infrastructure.git
└── docs/             copy contracts.md and ui-mockup.html here so the prompt's paths work
```

Backend setup:

```
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Set `JWT_SECRET_KEY` in `.env`. Set `FIRST_ADMIN_EMAIL` and `FIRST_ADMIN_PASSWORD` to get an admin. `OPENROUTER_API_KEY` is needed only for a real LLM; for the end-to-end pass set `ASSISTANT_LLM=fake`, which is refused in production.

Frontend setup: `cd frontend && npm ci`.

Tests:

```
cd backend && .venv/bin/python -m pytest -n auto -q --no-cov
cd backend && .venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .
cd frontend && npm run check && npm run build
```

Backend tests need no services. `npm run dev` runs mock mode; sign in with `example-admin@example.test` / `example-password`.

## geomind

The code was built against eeb80d9 of origin main, which still calls the removed `gm.plants.validate`. An adaptation commit was announced that replaces it and adds `save_chat_artifact` / `load_chat_artifact`. Pull origin main, run `tests/api/v1/assistant` and `tests/core/assistant`, and record the commit used. The scripted FakeLLM run (`ASSISTANT_LLM=fake`) depends on `save_profile` asking for approval: recheck it.

## Phase D status (D3)

Verified on the real local stack (see README, "Local stack") with geomind 0.3.0 (989cb59) and gemini 0.5.0 (217625e):

- Migrations 0001 to 0008 upgrade, downgrade and match the models on PostgreSQL 16 (`pytest -m postgres` with `POSTGRES_TEST_URL` on a scratch database).
- geomind's `check_run_store` (including chat artifacts) and `check_workspace` (plants, case with file bytes, documents) pass against the adapters. A chat artifact is a `run_artifacts` row with a null `run_id`. `design/<name>` is write-once inside geomind (`Session.save_artifact`), so the store only has to round-trip.
- Playwright golden path (`frontend/e2e/golden.spec.ts`), real and mock: sign in, import the seeded example as a project, overview, chat with the scripted run (it lists the project's plants, then asks approval), approve, runs and log, problem with one missing value, fill it, plant, study through Celery, results, report preview, Markdown and PDF, a project with a Persian name and its PDF, sign out.
- Bugs found and fixed: `run.started` of the routing run has no `loop` (frontend rejected the stream); `POST /design/case/validate` ignored the saved files (now takes `project`); the study kind schema asked for keys the backend sets; nested forms in the New study dialog; `Workspace` still had `plant()`; a chat artifact hit the run foreign key; login rejected reserved domains with a 422 (now a plain 401); mock studies never started.
- Not exercised: `read_case` from a real run (the scripted LLM only lists plants and saves a profile), a real LLM, `ASSISTANT_SANDBOX=docker` for module tests (the image `gemini-sandbox:0.5.0` builds and `DockerSandbox` runs in it).
- Open, see `.tmp/build/screen-diff.md`: missing marks on optional nested fields, sidebar progress dots stale after a study, KPI tile layout for missing values, plant palette length.

## What Phase D must still do

1. Merge the requests lists into `.tmp/build/requests.md`.
2. Fix the open items above.
3. Push both repos.

## Known mismatches to check first

Never exercised against each other; the frontend was built on mocks.

- `text.delta` replay: the backend sends one buffered `text.delta` without an id and expects the client to replace the step text; the reducer appends. Pick one and test a reload mid-step.
- Run ids in events are 32-character hex; the API uses dashed UUIDs. The frontend may compare them.
- Plant editor ports: `describe()` has port kinds but no route exposes them, so a module with no connection has no handles and ports are typed by name in the inspector. Add `inlets` and `outlets` (`[{port, kind}]`) to `palette` and `flowsheet.modules`; this is a contract change. Worth doing: the editor is weak without it.
- `GET /plant/flowsheet/schema` does not exist, so an empty plant can't be started; only templates.
- C7 assumptions: `layout` is `{id: {x, y}}`; `/plant/parameters` values are `{name: value}` and `missing` is a list of property names; gemini refuses bare numbers, so values are `{value, unit}`. Check the form sends that.
- C8 assumptions: `GET /design/study` is paged, `GET /design/results` and `/design/study/kinds` are arrays, `study.result` is an id or null, `study.error` is `{code, message}` or null.
- Activity `link`: the frontend opens `/projects/<id>/<route>[/<id>]`. Routes written are `study`, `results`, `report`, `assistant/runs`: confirm each maps to a real page. `study` and `results` do not match `design/study` and `design/results`.
- New project "copy another project's problem" is not built: no route in the contract.

## Known risks

- Done: the missing count is stored on each case version (`case_versions.missing`, migration 0007); project reads no longer call MinIO. Versions saved before 0007 count as 0 missing until the next save.
- A failed MinIO delete on project delete raises after the rows are gone.
- Nothing creates the MinIO bucket at startup; it is created on first write.
- Document extraction reads plain-text formats only. PDF and docx end `failed`.
- Assistant adapters still use raw Minio instead of `BlobStore`.
- The study router requires a MinIO dependency even when unused.
- Some gemini-heavy tests exceed the 1 s budget on a loaded machine.
