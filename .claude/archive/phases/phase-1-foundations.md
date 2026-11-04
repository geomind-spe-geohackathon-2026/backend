# Backend B1: Foundations (Claude Code prompt)

You work in the backend repo at `/Users/sahand/Desktop/crust-team/backend`. This prompt builds phase B1: admin user management, projects with owner-or-admin access, export and import, versioned plant models stored in gemini's own format, the `core/gemini` boundary, stable error codes, import boundary tests and the compose stack.

Work step by step. Commit after each step. Do not push until told.

## 0. Parallel sessions

Other Claude Code sessions work at the same time on the sibling repos (`../gemini`, the agent package `../geomind`, `../frontend`). That is expected and fine. What must not happen is two sessions working on **this** repo at once. So:

1. **At the start:** run `git status` and `git log -5` in the backend repo. If there are uncommitted changes, or a file `.tmp/session.lock` exists, stop and ask Sahand; another session may be working here. Otherwise write `.tmp/session.lock` with the time and a one-line note of this task.
2. **Before each commit:** run `git status` again. If files changed that you did not touch, or `git log` shows commits you did not make, stop and ask. Never commit, revert or stash someone else's changes.
3. **At the end** (or when you stop to ask): delete `.tmp/session.lock`.
4. **Writes stay inside the backend repo**, with one exception: step 7 writes `../infrastructure/`. Before writing there, run the same `git status` check in that folder (if it is a git repo) and stop if it has changes you did not make.
5. **Sibling repos are read-only.** They may change while you work: if gemini's API seems to differ from what you read earlier, read its docs again before assuming a bug.

## 1. Read first

1. `AGENTS.md`, `docs/CONVENTIONS.md`, `docs/DEVELOPMENT.md`, and every existing file under `src/` and `tests/`. Learn the current patterns (routers, schemas, services, repositories, settings, errors, tests) and follow them. Add to the structure; do not reorganise it.
2. `../docs/feature-map.md`, domains `identity` and `workspace`, if it exists.
3. In `../gemini`: `AGENTS.md` and its docs folder (`.claude/docs/`), especially the public API, modules and legacy docs, and the `Module` methods `to_dict`, `from_dict`, `save`, `load`. Read only; never change the gemini repo.

The API this phase builds is written out in section 6 of this prompt; that section is the contract for B1. If `../docs/contracts.md` exists and differs from it on these routes, follow this prompt and report the difference. The assistant routes are not part of B1.

**gemini is being restructured in parallel:** `gemini/core/` is going away (its sub-packages move to the top level) and `data` and `legacy` move under `gemini/utils/`. The public names of `import gemini as gm` stay. So the backend uses **only the public API** (`import gemini as gm`, `gm.<name>`, `gm.errors.<name>`), never a `gemini.core.*` or other internal path. If something the backend needs is not public, stop and say so; do not reach into internals.

If something this prompt needs does not exist (for example gemini has no example plant, or the current tests work differently than assumed here), stop and say so instead of guessing.

## 2. Rules

### Structure

- Features: `src/api/v1/<domain>/<feature>/{router,schemas,services,jobs}.py`, only the files a feature needs.
- One function in `services.py` per use-case, named after it: `create_project`, `export_project`, `change_user_role`.
- Models and repositories live in `src/core/clients/postgres/{models,repositories}/`, as `user` already does.
- Features never import each other. Shared data goes through repositories.
- `gemini` is imported only in `src/core/gemini/`. The agent package `geomind` (`import geomind as gd`) will be imported only in `src/api/v1/assistant/runs/adapters/` (B2). No physics formulas anywhere in the backend.
- Folder names: one word, lower case, no underscores.
- Routes and payloads exactly as in section 6. If one must change, stop and say so.

### Code quality

- Simple, readable, just enough code. No dead or speculative code: nothing for B2 or later.
- Nesting at most 3 levels; functions about 40 lines at most; guard clauses instead of nested ifs.
- Full-word names (`project`, not `prj`; `version`, not `ver`).
- No comments inside code. Explanations go in docstrings. Tool directives (`# noqa`) are allowed.
- Times are timezone-aware, stored and returned in UTC.
- Secrets are never returned to the browser and never logged.

### Tests

- Fast and targeted while working: run only the tests of the changed code and of everything that imports it, in parallel (`pytest -n auto` on those paths).
- Before each commit: the full fast suite, in parallel.
- Never call the network in tests.
- New tests mirror the source tree: `tests/api/v1/<domain>/<feature>/test_<usecase>.py`, `tests/core/<package>/test_<module>.py`. Existing tests stay where they are.
- Database in tests: follow how the current tests already work. If they need a running Postgres, add SQLite in memory for the fast suite with portable column types (`JSON().with_variant(JSONB, "postgresql")`, timezone-aware datetimes), and a `postgres` pytest marker that runs the repository tests against the compose Postgres; the marker is skipped by default. Say which way you chose and why.
- Redis in tests: `fakeredis`.
- gemini in tests: the real package with its example plant (it is local and fast).

### Working

- Temporary files go to `.tmp/` (git-ignored). Only lasting docs go to `docs/`.
- Update `AGENTS.md` and `docs/` in the same commit as the change they describe, so a new session knows the current state.
- Subtasks and subagents use lighter models (sonnet or haiku), not the main model.
- If something is missing, unclear or risky, stop and say so.

## 3. Steps

### Step 1: errors and access

- Error body exactly as in section 6: `{"error": {"code", "message", "details"}}`. Use the stable codes listed in section 6. Request validation errors become `422 validation_failed` with `details = {"fields": {"<field>": "<message>"}}`. Lists (users, projects) follow section 6: `{"items", "next"}` with `?cursor=` and `?limit=`. Reuse `src/core/errors.py`; extend it, do not replace it.
- `src/core/security/`: an admin dependency (`require_admin`) and `access.py` with `require_project(project_id, user)`. Rule: the owner or an admin may read and change a project. For anyone else the answer is `404 project_not_found`, the same as a missing project, so ids cannot be probed. Every route that takes a project id uses it. Sharing with other users comes later and will change only this function.

Tests: admin and member against an admin route; owner, admin, other member and a missing id against `require_project`.

### Step 2: identity/users

- `user` gets `active` (boolean, default true), with a migration. Inactive users cannot sign in or refresh, and their existing tokens are refused. Users are deactivated, never deleted, so authorship stays valid.
- Make sure `POST /identity/authn/refresh` works as listed in section 6. It probably exists already; if not, add it.
- The first admin is created at startup from settings if no admin exists (email and password from settings, never logged). Keep it if it already exists.
- Feature `src/api/v1/identity/users/`: `GET /identity/users` (list), `POST /identity/users` (create, `{email, name, password, role}`, duplicate email is `409 conflict`), `PATCH /identity/users/{id}` (`{role?, name?, active?}`). Admin only. An admin cannot deactivate themselves or remove their own admin role (`409 conflict`), so the system never loses its last admin by accident.
- `user = {id, email, name, role, active}` everywhere a user is returned.

### Step 3: workspace/projects

- Model and repository `Project`: `id` (uuid), `name`, `owner_id`, `created`, `updated`. Migration for `projects`.
- Feature `src/api/v1/workspace/projects/`: list, create, get, delete, as in section 6. A member lists their own projects; an admin lists all. Deleting a project deletes everything inside it (`on delete cascade`).
- `project = {id, name, owner: {id, name}, plant_version, created, updated}`. `plant_version` is the latest plant version number or `null` (add it in step 4).

### Step 4: plant versions and core/gemini

**Storage.** Model and repository `PlantVersion`, migration for `plant_versions`:

```text
plant_versions
  id            uuid
  project_id    fk projects, on delete cascade
  number        int, unique together with project_id, starting at 1
  plant_type    text, copied from content["plant_type"]
  content       json (jsonb on Postgres), exactly gemini's plant to_dict() output
  digest        text, sha256 of the canonical JSON (sorted keys, no spaces)
  note          text
  author_id     fk users
  created       timestamptz
```

Rows are never updated. Repository functions: `save_version(project_id, content, note, author_id)` (next number; refuses content whose digest equals the latest version's with `409 conflict`, so there are no empty versions; two concurrent saves must not get the same number, so rely on the unique constraint and retry once), `latest_version(project_id)`, `version_by_number(project_id, number)`, `list_versions(project_id)` (without `content`).

Why one JSON per version: gemini's format already holds dated parameters (`param_history`) and tag bindings per module, and gemini validates the whole file on load. A second, split format would have to be kept in sync with gemini forever.

**`src/core/gemini/`**, the only backend folder that imports gemini. Add gemini as an editable path dependency on `../gemini`. Plain functions in `src/core/gemini/plant.py`, no class:

```python
load_plant(content)       # stored content -> gemini plant; resolves plant_type, calls from_dict
dump_plant(plant)         # gemini plant -> content (to_dict)
validate_content(content) # load then dump; returns the normalised content
example_plant()           # content of the example doublet that gemini ships
```

- **Resolving `plant_type`:** it comes from stored or uploaded JSON and names a class. Never import an arbitrary string. Resolve it only against classes that `import gemini as gm` exposes publicly and that are gemini plants (find the base class in gemini's docs), by matching the class path that `to_dict` writes. Because gemini is moving files, a stored class path can change: if gemini documents a stable plant identifier or a lookup function, use that; if not, report it as a risk (old stored versions would stop loading after the restructure) and propose the smallest fix in gemini.
- Anything that does not resolve is `422 plant_invalid`. Every gemini error (`gm.errors.*`, Pydantic validation) becomes the same `plant_invalid` with gemini's message in `details`.
- Services never call gemini directly; they call `core/gemini`.

No plant routes in B1 (they come in B3). Step 5 uses these functions for export and import, and tests use them directly.

Tests: `example_plant()` round-trips through `load_plant` and `dump_plant` unchanged; a stored version round-trips through the repository and `core/gemini` unchanged; a `plant_type` outside gemini, a non-plant class, wrong module paths and a wrong format version are each `plant_invalid`; saving identical content twice is a conflict.

### Step 5: export and import

- `GET /workspace/projects/{id}/export` returns a zip:

```text
project.json        {"format": 1, "name": ..., "exported": <UTC time>}
plant/<number>.json {"number", "note", "created", "content"}   one file per version
```

- `POST /workspace/projects/import` (multipart `file`) creates a new project owned by the caller from such a zip. Every version is checked with `validate_content` before anything is written; one bad version refuses the whole import (`422 plant_invalid`, the file name in `details`). The import runs in one transaction.
- Zip safety: refuse paths with `..` or absolute paths, refuse more than a size limit from settings (unpacked size, not only upload size), read only the expected file names.
- Legacy project zips: check gemini's legacy docs. If gemini exposes a public legacy converter that turns a legacy project folder into plant content in a few lines through `core/gemini` (`convert_legacy(folder)`), accept a legacy zip too and store the result as version 1 with note "Imported from legacy project". If it is not public or needs more than that, do not build it; report what it would take.

Tests: export then import gives the same versions; a zip with `../` is refused; a bad version refuses the import and writes nothing.

### Step 6: import boundary test

`tests/test_boundaries.py`, an AST scan of `src/`:

- only files under `src/core/gemini/` import `gemini`, and they import only `gemini` itself or `gemini.errors`, never deeper paths;
- only files under `src/api/v1/assistant/runs/adapters/` import `geomind` (passes trivially now);
- no file under `src/api/v1/<domain>/<feature>/` imports another feature.

The test must fail with the file and the import it found.

### Step 7: compose stack

`../infrastructure/compose.yml` (create the folder if needed; if a compose file already exists there or in the backend, extend it and say which one is the source of truth): `postgres`, `redis`, `influxdb`, `minio`, `chromadb`, `api`, `worker`, `frontend`.

- `api` and `worker` use the same backend image with different commands. The image needs `../gemini` (and later `../geomind`): set the build context to `crust-team/` and copy the sibling repos, or say clearly why another way is better.
- `api` runs the migrations before it starts.
- `frontend` builds `../frontend`; if it has no Dockerfile yet, leave the service in with a clear note in the docs and do not invent one.
- Settings come from an `.env` file; commit `.env.example` with every variable and no real secret.
- Health checks on postgres, redis and api, and `depends_on` with `condition: service_healthy`.

Check: `docker compose config` passes. If Docker is available, `docker compose up` starts the stack and `GET /api/v1/system/health` answers; otherwise say that you could not run it.

### Step 8: docs

Update in the same commits as the code:

- `AGENTS.md` "Start here": the new folders, the import rules (public gemini API only), the error codes, how plant versions are stored and why, how to run the stack.
- `docs/CONVENTIONS.md`: feature folders, one service function per use-case, `require_project` on every project route, `core/gemini` as the only gemini import, no comments in code.
- `docs/DEVELOPMENT.md`: the test tiers and commands, the `postgres` marker, compose.

## 4. Done when

- Every route in section 6 works and is tested.
- A plant version round-trips through the repository and `core/gemini` unchanged.
- Export then import gives the same project.
- The boundary test passes.
- `docker compose config` passes (and `up` if Docker was available).
- The full fast suite passes in parallel.
- Docs describe the new state.

## 5. Report back

- What was built, step by step, with the commits.
- The test database choice and why.
- How `plant_type` is resolved, and whether the gemini restructure can break stored versions.
- Whether legacy import was built, and if not, what it would take.
- Any contract change you think is needed (do not make it yourself).
- Anything the frontend should know.
- Anything missing, unclear or risky that you noticed.
- Whether you met another session's changes in the backend or infrastructure repo.

## 6. API contract for B1

This is the part of the shared contract (`contracts.md`, version 9) that B1 builds. The frontend builds against the same text.

General:

- Base `/api/v1`, JSON. Times are ISO 8601 with a timezone, UTC.
- Path = `/<domain>/<feature>/...`, the same names as the folders.
- Auth: bearer access token; renewed with `POST /identity/authn/refresh`. Tokens never go in URLs.
- Errors: `{"error": {"code": "<snake_case>", "message": "<human text>", "details": {...}}}` with a matching HTTP status. Codes are stable; messages may change.
- Stable codes: `unauthorized` (401), `forbidden` (403), `not_found` and `<thing>_not_found` (404), `validation_failed` (422, `details = {"fields": {"<field>": "<message>"}}`), `conflict` (409), `plant_invalid` (422), `rate_limited` (429), `internal` (500). A project the caller may not see answers `404 project_not_found`, the same as a missing one.
- Lists: `{"items": [...], "next": "<cursor or null>"}`; the next page is `?cursor=<next>`, optional `?limit=` (default 50).

identity:

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

workspace/projects:

| Method | Path | Body → Response |
|---|---|---|
| GET | `/workspace/projects` | → list of `project` |
| POST | `/workspace/projects` | `{name}` → `project` |
| GET | `/workspace/projects/{id}` | → `project` |
| DELETE | `/workspace/projects/{id}` | → `204` |
| GET | `/workspace/projects/{id}/export` | → zip file |
| POST | `/workspace/projects/import` | multipart `file` → `project` |

`project = {id, name, owner: {id, name}, plant_version, created, updated}`; `plant_version` is the latest plant version number or `null`. Only the owner or an admin may read or change a project.

Export zip: `project.json` (`{format: 1, name, exported}`) and `plant/<number>.json` (`{number, note, created, content}`, `content` in gemini's plant format), one file per plant version. Import takes the same zip.
