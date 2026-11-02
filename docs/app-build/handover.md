# Handover: Phase D of the app build

Read this first, then `app-frontend-backend.md` sections 1 and 7 to 10. Phases A, B and C are done. Phase D has not started.

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

## What Phase D must do

1. `.venv/bin/python scripts/to_openapi.py`, then `npm run gen:api`. Generated names differ from the placeholder. Delete the hand-written path and type blocks: `src/shared/sse/paths.ts`, `src/domains/identity/paths.ts`, `src/domains/workspace/paths.ts`, `src/shared/api/design.ts`, `src/shared/api/design-paths.d.ts`, the `declare module` blocks in `domains/design/{case,plant}/types.ts`, and types in `shared/sse/contract.ts` that the generated schema has. Fix `src/shared/api/types.ts`. Mocks then import generated types.
2. Resolve the OpenAPI `Progress` clash between design/study and core/progress.
3. Bring up the stack and run one Playwright golden path in real mode and in mock mode (section 7, item 2). Compare screens with the mockup screenshots: rerun the capture, because `frontend/.tmp` is not in git.
4. Full fast suites, lint, types, no-comments and boundary tests.
5. Leave the full stack running for the owner, seeded with one admin and one example project, and report the address, login, and stop and start commands.
6. Final report, section 10 of the prompt.

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

- Project reads call MinIO through `ProgressReader`: a missing blob fails the read, and the project list reads case files per project, which may be slow. Consider computing `missing` at save.
- A failed MinIO delete on project delete raises after the rows are gone.
- Nothing creates the MinIO bucket at startup; it is created on first write.
- Document extraction reads plain-text formats only. PDF and docx end `failed`.
- Assistant adapters still use raw Minio instead of `BlobStore`.
- The study router requires a MinIO dependency even when unused.
- Some gemini-heavy tests exceed the 1 s budget on a loaded machine.
