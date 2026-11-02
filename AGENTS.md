# Agent Instructions

Read [docs/CONVENTIONS.md](docs/CONVENTIONS.md) for project-wide work.

Only when a task creates, modifies, reviews, or tests code, also read and follow
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). Do not read the development guide for
non-code tasks.

## Start here

FastAPI backend for the geothermal digital twin. Routes and payloads follow
`../docs/contracts.md`; change that file first, never a route on its own.

- **Features** live in `src/api/v1/<domain>/<feature>/`, with only the files they need
  out of `router.py`, `schemas.py`, `services.py` and `tasks.py`. Today: `system/health`,
  `identity/{authn,me,users}`, `workspace/projects`. One function in `services.py` per
  use-case.
- **Storage:** models and repositories in `src/core/clients/postgres/`.
- **Access:** `src/core/security/access.py`. `CurrentUser` and `AdminUser` on routes,
  `AccessibleProject` (`require_project`) on every route that takes a project id.
- **gemini:** only `src/core/gemini/` imports it, and only the public API
  (`import gemini as gm`, `gm.<name>`, `gm.errors.<name>`), never `gemini.core.*`.
  The agent package (`geomind`, public API only) is imported only in
  `src/api/v1/assistant/runs/adapters/`. Features never import each other.
  `tests/test_boundaries.py` enforces all of this.
- **Errors:** `{"error": {"code", "message", "details"}}`, raised as `AppError`
  subclasses. Stable codes: `unauthorized`, `forbidden`, `not_found`,
  `<thing>_not_found`, `validation_failed`, `conflict`, `plant_invalid`, `case_invalid`,
  `missing_inputs` (`details.missing`), `rate_limited`, `not_implemented` (501,
  `details.missing` names the gemini or geomind part that does not exist), `internal`.
- **Tables:** `docs/CONVENTIONS.md` section Tables lists them. Migration `0006` holds
  all app tables (case, chat, run, study, result, document, activity); each has a model
  and a base repository in `src/core/clients/postgres/`. Features add no tables.
- **Plant versions:** one row per saved plant in `plant_versions`, `content` being
  exactly gemini's `to_dict()` output (`src/core/gemini/plant.py`: `from_dict`,
  `to_dict`, `validate_content`; a bad document is `plant_invalid` with
  `details.problems`). gemini's format already holds dated parameters
  and bindings and is validated on load, so a second, split format would only have to
  follow it. Rows are never updated.
- **OpenAPI:** `openapi.json` at the repo root is committed; the frontend generates its
  types from it. After any route or schema change run
  `.venv/bin/python scripts/to_openapi.py`; `tests/test_openapi.py` fails when it is stale.
- **Jobs:** Celery tasks extend `src/core/jobs/task.py:BaseTask` (progress and cancel flag
  in Redis, bounded retries); studies are cancelled with `jobs.control.terminate`. See
  the Background tasks section of `docs/CONVENTIONS.md`.
- **Stack:** `../infrastructure/compose.yml` runs everything:
  `cd ../infrastructure && cp .env.example .env && docker compose up -d --build`. The
  backend image also needs the build context `geomind: ../geomind` (the Dockerfile
  copies it; `requirements.txt` has `-e ../geomind`).
- **Tests:** `.venv/bin/python -m pytest -n auto`, including the import boundary test,
  `tests/test_no_comments.py` (docstrings only, no comments in code)
  and `tests/test_route_guard.py`, which every new route must pass. See
  [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

Temporary files go to `.tmp/`, which is git-ignored. Lasting docs go to `docs/`.
