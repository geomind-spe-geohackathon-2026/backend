# Backend: brief for the design thread

This file hands the backend work to a new thread. It holds everything decided so far, what is still open, and how Sahand likes to work. Read all of it before replying.

## 1. What the backend is

The FastAPI backend of the new GEMINI system, built for the SPE Europe Energy GeoHackathon. It replaces the legacy GEMINI Flask app. It owns users, projects, the stored plant models, time series, background jobs and the live stream to the browser. It holds no physics (that is the `gemini` package) and no agent logic (that is the `geomind` package).

The competition: Challenge 1 is an agentic AI workflow driving GEMINI; Challenge 2 is an integrated deep-geothermal heating and cooling design with the agent log (prompts, answers, token usage). For the competition the backend's critical part is the assistant (chat and agent runs).

## 2. Where it sits

```
crust-team/                      (Sahand's machine: /Users/sahand/Desktop/crust-team)
├─ infrastructure/   docker-compose
├─ frontend/         React + Vite + Tailwind
├─ backend/          this repo
├─ geomind/          agent package
└─ gemini/           physics and engine

frontend → backend → geomind → gemini
```

- The frontend talks to the backend only through the HTTP API and SSE events in `contracts.md`.
- The backend uses geomind through three interfaces it implements (`LLM`, `RunStore`, `Workspace`), plus callbacks and hooks, and calls `gd.Run(...)`.
- The three repos are built in parallel. Each builds against `contracts.md`, never against another repo's code; mocks and `FakeLLM` stand in until the other side exists.

## 3. The current repo (keep it, extend it)

Sahand does not want the existing structure changed much:

```
backend/
├── AGENTS.md  README.md  pyproject.toml  Dockerfile  compose.yml  alembic.ini
├── alembic/versions/0001_create_users.py
├── docs/CONVENTIONS.md  docs/DEVELOPMENT.md
├── src/
│   ├── main.py  fastapi.py  celery.py
│   ├── api/v1/
│   │   ├── identity/  authn/  me/          (router, schemas, services, jobs)
│   │   └── system/    health/
│   └── core/
│       ├── settings.py  errors.py  lifespan.py  middlewares.py
│       ├── logging/  ratelimit/  security/ (jwt, passwords, middleware, paths)
│       └── clients/
│           ├── postgres/  client, models/user.py, repositories/{base,user}.py
│           ├── redis/     client, models/{rate_limit,revoked_access_token}, repositories/
│           └── chromadb/  influxdb/  minio/  openrouter/
└── tests/  test_app, test_identity, test_main, test_repositories, test_security
```

## 4. Decisions already made

- **Feature folders:** `src/api/v1/<domain>/<feature>/{router,schemas,services,jobs}.py`, only the files a feature needs. One service function per use-case, named after it (`create_project`, `calibrate_pump`).
- **Domains and features** (names from `feature-map.md`; one word, lower case, no underscores; the same in the frontend and in the URL):

```
identity/    authn  me  users
system/      health
workspace/   projects  documents  guide
assistant/   chat  runs
plant/       flowsheet  parameters  bindings  catalogue
timeseries/  dashboard  trends  sources  availability  softsensors
performance/ nodal  injectivity  pump
integrity/   (after the hackathon)
reporting/   operations  (regulatory after the hackathon)
```

- **Boundaries:**
  - Features never import each other. Shared data goes through repositories in `core/clients/postgres/repositories/`.
  - `gemini` is imported only in `src/core/gemini/` (stored plant ↔ gemini plant). No physics formulas anywhere in the backend.
  - `geomind` is imported only in `src/api/v1/assistant/runs/adapters/` (`llm.py`, `store.py`, `workspace.py`, `events.py`, `hooks.py`).
  - Tests enforce both import rules.
- **Assistant flow:** posting a message stores it, creates a `queued` run and enqueues a Celery job; the job builds `gd.Run` with the adapters; geomind callbacks publish events to Redis; the SSE route streams them (replay from `Last-Event-ID`). A hook can pause a run (`waiting`); `POST /runs/{id}/answer` resumes it from its checkpoint; cancel stops it. The full log (prompts, answers, tool calls, tokens) is stored and served.
- **Split of responsibilities:** backend = storage, access, queue, live stream (where and who); geomind = understanding, loop choice, tools, memory (what and how). The backend never picks a loop or an agent.
- **SSE, not WebSocket:** the live stream is one way; user actions are plain POSTs.
- **Plant model storage:** Postgres, JSON content with a version table, in gemini's own plant format. Not git folders as in the legacy app (recommended; confirm with Sahand).
- **Legacy lessons to keep:** owner-or-admin check on every project route (legacy had almost none), secrets never returned to the browser, timezone-aware times (UTC in the API), long jobs with progress, timeout and failure state, one tally upload (legacy had two), equipment links from the flowsheet connections (legacy used "first upstream unit").
- **Phases:** B1 foundations (users, projects, plant versions, core/gemini, compose), B2 assistant, B3 plant and time series, B4 well performance.

## 5. Open questions to think through

Think them through, propose, and discuss with Sahand before writing any prompt.

1. **Plant model storage** in detail: one JSON per version or split tables; how parameters and bindings with dated versions fit; how a version maps to gemini's `to_dict`/`from_dict`.
2. **core/gemini:** its exact API (load a plant, list modules for the palette, run a calculation) and how heavy calculations run on workers.
3. **Runs and events:** table design for runs, events, checkpoints and usage; event ordering and replay; retention.
4. **Jobs:** one Celery pattern for every long calculation (progress, timeout, cancel, failure) shared by `runs`, `softsensors` and `performance`.
5. **Access model:** roles (`admin`, `member`), project ownership, sharing a project with other users or not.
6. **Documents and search:** MinIO for files, ChromaDB for search, how `Workspace.documents()` serves the assistant.
7. **Time series:** InfluxDB layout (measured, filtered, calculated tags), CSV import format, historian connection.
8. **Tests:** layout mirroring `api/v1`, fixtures, how geomind and gemini are faked in fast tests.
9. **contracts.md:** check the routes and payloads of steps 1 and 2 against the design and propose changes.

## 6. Files to read

In the project folder:

- `phases/README.md`: all phases, shared rules.
- `phases/contracts.md`: HTTP API, live events, geomind interfaces.
- `phases/backend/phase-1-foundations.md` to `phase-4-performance.md`: phase drafts; the design thread may change them.
- `frontend/feature-map.md`: domains, features and use-cases with legacy frontend and backend IDs.
- `geomind/brief.md`: the geomind side, for the interfaces.

On Sahand's machine (ask him to attach if needed): `crust-team/gemini-legacy-backend-analysis/backend-features.md`, the inventory of the legacy Flask backend (98 features, 150 routes) with its risks.

## 7. How Sahand works

- Writes in Persian; reply in Persian. Start every line with a Persian word, put English names in code blocks or follow them with a right-to-left mark, keep mixed lines short.
- This thread designs and writes prompts. Sahand runs the work in Claude Code on his own machine. Do not write code in a repo or push anything.
- During design talk, discuss only. Write or hand over a prompt only when Sahand says «go».
- Names matter a lot to him. Give every name a reason; prefer industry terms; avoid vague words. Folder names one word, no underscores.
- He wants the existing backend structure kept, the API simple, and complexity hidden.
- Code quality bar for every prompt: simple and readable, just enough code, nesting at most 3, functions about 40 lines, no dead code, no comments inside code (docstrings only), guard clauses, full-word names.
- Every prompt: fast targeted tests while working (only changed code and its importers, in parallel), full fast suite before commit, never the network in tests; temporary files in `.tmp/`; update `AGENTS.md` and docs in the same commit; subagents use lighter models; say so when something is missing or risky; commit per step, no push until told.
- He accepts what he does not object to, but says clearly when he disagrees. Recommend one option; do not list many.

## 8. The first goal of the new thread

Design the backend in depth with Sahand, answering section 5. When he says «go», write the Claude Code prompt for phase B1 into `phases/backend/` (updating `phase-1-foundations.md` or replacing it), following section 7.
