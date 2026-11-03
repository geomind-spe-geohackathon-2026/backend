# Handover: Phase D of the app build

Current state, production pins and open work: `status.md`.

Read this first, then `app-frontend-backend.md` sections 1 and 7 to 10. Phases A, B, C and the integration pass (D3) are done; see Phase D status.

In a new clone the prompt's `../docs/` paths do not exist, because `docs/` was never a git repo. Their files are here: `contracts.md` (version 41, wins over the prompt), `ui-mockup.html`, `app-frontend-backend.md`, `plan.md` (gap decisions), `requests.md` (ready to paste), `inventories/`.

## New machine

Tools: Python 3.12, Node 22 with npm, Docker with compose, git over SSH with access to the repos below.

gemini is the released wheel pinned by URL in `requirements.txt`, never `-e`: 0.5.14. It releases from gemini's `dev`. geomind is the released 0.4.21 wheel pinned by URL and sha256, never 0.4.12; `../gemini` is not needed. See README, "Docker", for bumping a pin. `stack-up.sh` pulls `ghcr.io/geomind-spe-geohackathon-2026/gemini-sandbox:<version>` and tags it `gemini-sandbox:<version>`, the name geomind expects, when it is absent. The local stack runs on Windows WSL2 with Docker Desktop; if the shell predates the `docker` group, run `sg docker -c "scripts/stack-up.sh"`. Do not copy `OPENROUTER_API_KEY` from `.env.example` into `.env`: its placeholder turns on the real LLM. Without root, Playwright's Chromium needs its libraries unpacked from `apt-get download` and named in `LD_LIBRARY_PATH`.

Folder layout (gemini and geomind are only needed as checkouts to read them):

```
geomind-spe-geohackathon-2026/
├── backend/          git@github.com:geomind-spe-geohackathon-2026/backend.git
├── frontend/         git@github.com:geomind-spe-geohackathon-2026/frontend.git
├── gemini/           git@github.com:geomind-spe-geohackathon-2026/gemini.git   branch dev, 0.5.4 (a3b1471)
├── geomind/          git@github.com:geomind-spe-geohackathon-2026/geomind.git                     branch main, 0.4.1 (c9a5c1c)
├── infrastructure/   git@github.com:geomind-spe-geohackathon-2026/infrastructure.git
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

0.4.0 is in: readers skip unknown event types (`adapters/replay.py`), `study.recorded` adds a `done` study without a result (`StudyRecorder`), `DatabaseUsageLedger` sums finished runs, and `project.budget` adds `gd.hooks.ProjectBudget` only when a cap is set. FakeLLM runs no study tool, so the event and the budget stop are tested at adapter level only.

## Phase D status (D3)

Verified on the real local stack (see README, "Local stack") with geomind 0.3.0 (989cb59) and gemini 0.5.0 (217625e):

- Migrations 0001 to 0008 upgrade, downgrade and match the models on PostgreSQL 16 (`pytest -m postgres` with `POSTGRES_TEST_URL` on a scratch database).
- geomind's `check_run_store` (including chat artifacts) and `check_workspace` (plants, case with file bytes, documents) pass against the adapters. A chat artifact is a `run_artifacts` row with a null `run_id`. `design/<name>` is write-once inside geomind (`Session.save_artifact`), so the store only has to round-trip.
- Playwright golden path (`frontend/e2e/golden.spec.ts`), real and mock: sign in, import the seeded example as a project, overview, chat with the scripted run (it lists the project's plants, then asks approval), approve, runs and log, problem with one missing value, fill it, plant, study through Celery, results, report preview, Markdown and PDF, a project with a Persian name and its PDF, sign out.
- Bugs found and fixed: `run.started` of the routing run has no `loop` (frontend rejected the stream); `POST /design/case/validate` ignored the saved files (now takes `project`); the study kind schema asked for keys the backend sets; nested forms in the New study dialog; `Workspace` still had `plant()`; a chat artifact hit the run foreign key; login rejected reserved domains with a 422 (now a plain 401); mock studies never started.
- Not exercised: `read_case` from a real run (the scripted LLM only lists plants and saves a profile), a real LLM, `ASSISTANT_SANDBOX=docker` for module tests (the image `gemini-sandbox:0.5.0` builds and `DockerSandbox` runs in it).
- Open, see `.tmp/build/screen-diff.md`: missing marks on optional nested fields, sidebar progress dots stale after a study, KPI tile layout for missing values, plant palette length.

## State after the WSL move (2026-11-02)

- Verified: backend 504 tests, frontend 957 tests, Playwright real. Migrations 0001 to 0009 on PostgreSQL 16 were last run on 0.5.1.
- `tests/test_versions.py` checks that the installed engines are the versions pinned in `requirements.txt` and that nothing is editable.
- `backend/.env` is for tests, `.env.dev` for the local stack, `.env.production` for deploys. Compose: `compose.dev.yml` and `compose.yml`.
- Requests: `gemini-requests.md` for gemini, `requests.md` for geomind.
- `size` is a study kind (method `run`, `prepare: ["size"]`); the example project seeds `HeatingFullCoolingPlant` (`tests/fixtures/hackathon/seed_plant.json`), feasible once the case is complete.
- `src/core/problems.py:readable` rewords gemini's range text; gemini should give bounds as data, see the request in `requests.md`.
- Open: report images (flowsheet and charts) and cost sources in the report, requirement quantity and unit choices from `gm.plants.roles()`, a green scripted `save_profile` (its one-point profile is refused).
- Could not reproduce on this machine: mock golden-path failure, empty Overview after creating a project.

## State after the production move (2026-11-02)

- geomind.team runs from main on this laptop; the app is tested there. Any fix needs a production rebuild, done by the hosting thread. Dev volumes were deleted after the move.
- The assistant runs on DeepSeek only: `ASSISTANT_MODEL_PREFIX` refuses any other model before a real run starts. Set `GEOMIND_MODEL`, `GEOMIND_CHEAP_MODEL` and `GEOMIND_PROVIDER` in `.env.dev` and `.env.production`.
- `python -m scripts.projects export --project <id> --out bundle.tar` and `import bundle.tar --owner <email>` move whole projects: rows and objects, ids kept, users remapped to one owner, refused if an id exists. A new table with no rule in `rows_of_table` stops the tool.
- The report draws a process diagram (`frontend/src/shared/plant/flowsheet-sheet.ts`, `flowsheet-layout.ts`) and, in the appendix, the full flowsheet on a landscape PDF page. Modules merge only when type, connections and settings are equal.
- A failed chat run names an internal error and links the studies it recorded; the raw message stays in the run log. Any `stop_reason` of `error` reads this way, a model provider failure included.
- Branch `registry-packages` installs the engines from a registry, waiting for its URL and versions. geomind requests are in `requests.md`, among them the crash at `loops/design.py:293`.

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
