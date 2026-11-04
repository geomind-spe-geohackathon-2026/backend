# Handoff: BACKEND I (2026-11-04 00:00 UTC)

Thread: BACKEND I (backend only; frontend work goes to the frontend thread through the coordinator). Reply to Sahand in Persian.

## Where things stand

- Production: backend v1.1.5 (67e9884), geomind 0.4.21, gemini 0.5.14, migration 0013. Frontend 1.1.17+.
- Backend `dev` is 6 commits ahead of `main`, at v1.1.6 (fc4a5a1 and later), 642 tests pass, NOT deployed:
  - next-step suggestions: `message.suggestions` (migration 0014), `GET /assistant/suggestions?project=&chat=`, `suggestions` on an empty chat's state, `Workspace.project_state(project_id)` for geomind;
  - `ASSISTANT_MODEL_PREFIX` takes a comma-separated list;
  - a sandbox is passed only to a geomind that takes one (geomind 0.4.22 has none).
- Release plan for geomind 0.4.22 + gemini 0.6.1: backend `docs/app-build/status.md`, section "Next geomind release". It lists every env line (17 `GEOMIND_<ROLE>_MODEL`, evolve, steps, concurrency, MCP timeout), the cost catalogue re-seed (133 rows), and the nemotron switch.

## Waiting on

- Sahand's go for the geomind 0.4.22 release, then: pin geomind 0.4.22 and gemini 0.6.1 by URL and sha256, set the env, merge dev to main, deploy through the Deploy thread, re-seed the catalogue (`python -m scripts.knowledge add cost-sources.csv --by admin@geomind.team`), and tag.
- Sahand's choices: retries (5/2 now vs 3/0.5 in geomind's tests); provider (`deepseek` instead of `relace/fp4`) if DeepSeek stays.
- GEOMIND II's nemotron comparison (`nvidia/nemotron-3.5-super-vl:free`): then every role model, `ASSISTANT_MODEL_PREFIX=nvidia/nemotron-`, no `GEOMIND_PROVIDER`, `GEOMIND_CONTEXT_WINDOW=200000`, `GEOMIND_MAX_OUTPUT_TOKENS=16000`; concurrency and retries from geomind's measurements (free model: about 20 requests a minute, 1000 a day).
- geomind must put `suggestions` on `RunResult` too, or the backend reads them from `run.finished` (today it reads `RunResult.suggestions` with getattr).

## How to work (rules)

- New work on `dev`, unit tests only (no local stack: Sahand), `git push origin dev:main` when tests pass, deploy only through the Deploy thread via the coordinator. A schema migration needs Sahand's own go.
- Versions: `src/version.py`, `CHANGELOG.md`, tag `v1.1.x` on main after each deploy; only the patch goes up.
- Stage by explicit path (`git add -A -- <paths>`), lint (`ruff check`, `ruff format`), `python scripts/to_openapi.py` when routes change.
- No comments in code; geomind is imported only in `src/api/v1/assistant/runs/adapters/` and `src/core/geomind/`.
- Work in fresh small sessions (memory: fresh-sessions-for-work).
