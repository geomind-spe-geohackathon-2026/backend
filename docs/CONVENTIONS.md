# Project Conventions

## General

- Keep project documentation concise and in English.
- Keep documentation links relative so they work locally and on GitHub.
- Never place secrets or real environment values in documentation.
- Update documentation when commands, paths, or project structure change.

## API terminology

- A **domain** is a business or system area that groups related capabilities, such as `identity` or `system`.
- A **feature** is one focused capability inside a domain, such as `authn` inside `identity` or `health` inside `system`.
- A feature belongs to one domain and owns its endpoints, schemas, and services.

## Project structure

```text
src/
├── fastapi.py                # FastAPI application and runner
├── main.py                   # FastAPI and Celery service entry point
├── celery.py                 # Celery application and runner
├── api/
│   ├── __init__.py           # Root routers and tasks
│   └── v1/
│       ├── __init__.py       # Version routers and tasks
│       ├── system/           # Domain
│       │   ├── __init__.py   # Domain routers and tasks
│       │   └── health/       # Feature
│       │       ├── __init__.py
│       │       ├── router.py
│       │       ├── schemas.py
│       │       ├── services.py
│       │       └── tasks.py
│       ├── identity/         # Domain
│           ├── __init__.py   # Domain routers and tasks
│           ├── authn/        # Feature
│           │   ├── __init__.py
│           │   ├── router.py
│           │   ├── schemas.py
│           │   ├── services.py
│           │   └── tasks.py
│           ├── me/           # Feature
│           │   ├── __init__.py
│           │   ├── router.py
│           │   ├── schemas.py
│           │   ├── services.py
│           │   └── tasks.py
│           └── users/        # Feature
│               ├── __init__.py
│               ├── router.py
│               ├── schemas.py
│               └── services.py
│       └── workspace/        # Domain
│           ├── __init__.py   # Domain routers and tasks
│           └── projects/     # Feature
│               ├── __init__.py
│               ├── router.py
│               ├── schemas.py
│               └── services.py
└── core/
    ├── clients/
    │   ├── chromadb/client.py
    │   ├── influxdb/client.py
    │   ├── minio/client.py
    │   ├── openrouter/client.py
    │   ├── postgres/
    │   │   ├── client.py     # PostgreSQL connection
    │   │   ├── models/       # SQLAlchemy models
    │   │   └── repositories/ # Database access
    │   ├── redis/
    │   │   ├── client.py     # Redis connection
    │   │   ├── models/       # Redis data models
    │   │   └── repositories/ # Redis data access
    │   └── errors.py          # Shared client errors
    ├── errors.py             # Application errors and error middleware
    ├── gemini/               # The only package that imports gemini
    │   ├── errors.py
    │   └── plant.py          # from_dict, to_dict, validate_content
    ├── logging/
    │   ├── logger.py         # Logger configuration
    │   └── middleware.py     # Request logging middleware
    ├── pagination/
    │   └── page.py           # Cursor pagination for list endpoints
    ├── ratelimit/
    │   ├── errors.py
    │   └── middleware.py
    ├── security/
    │   ├── access.py         # current_user and require_admin dependencies
    │   ├── bootstrap.py      # First admin from settings
    │   ├── emails.py
    │   ├── errors.py
    │   ├── jwt.py
    │   ├── middleware.py
    │   ├── passwords.py
    │   ├── paths.py
    │   └── schemas.py        # The `user` response shared by identity features
    ├── lifespan.py           # Startup and shutdown
    ├── middlewares.py        # Middleware registration
    └── settings.py           # Environment settings
```

## API paths

- Place API features under `src/api/<version>/<domain>/<feature>/`.
- Build public paths as `/api/<version>/<domain>/<feature>[/<endpoint>]`.
- The version package owns `/api/<version>`.
- Each domain package owns its domain prefix and includes its feature routers.
- Each feature router owns its feature prefix and endpoints.
- Define OpenAPI tags on feature routers, using the feature name as the tag.
- Only features have standalone `router.py` and `tasks.py` files.
- API, version, and domain packages gather routers and tasks in `__init__.py`.
- Do not define feature endpoints directly in aggregation packages.

## Background tasks

- A *task* is the Celery code in `tasks.py`. A *job* is the record a user sees; jobs
  arrive later with their table.
- A feature with Celery tasks defines a `tasks.py` and exposes its module in
  `TASK_MODULES`. A feature has only the files it needs.
- Domain, version, and API `__init__.py` files gather `TASK_MODULES` from below.
- `src/celery.py` configures Celery and includes all gathered task modules.
- Run FastAPI with `python -m src.main --fastapi`.
- Run Celery with `python -m src.main --celery`.
- Run workers with `celery -A src.celery:app worker --loglevel=INFO`.
- Every task uses `core/jobs/task.py:BaseTask` (the app sets it as `task_cls`):
  `@shared_task(bind=True, name="<domain>.<feature>.<verb>")` in the feature's
  `tasks.py`, for example `design.study.run`. It retries only `ConnectionError` and
  `TimeoutError` with a bounded backoff, never an `AppError`, acks late, and has the time
  limits of `TASK_SOFT_TIME_LIMIT_SECONDS` and `TASK_TIME_LIMIT_SECONDS`.
- The job id is the study or run id. `self.report(job_id, done, total)` writes progress to
  Redis (`job:<id>:progress`); the API reads it with `JobRepository.progress`. A task
  calls `self.check_cancelled(job_id)` between steps; the API sets the flag with
  `jobs.control.request_cancel`. State expires after `JOB_STATE_TTL_SECONDS`.
- A task that cannot check a flag (a study, because gemini's study functions take no
  cancel check) is stopped with `jobs.control.terminate(task_id)`: Celery revoke with
  terminate. Store the task id on the study row.
- A task body calls one `services.py` function; it opens its own session and Redis
  client, and runs async code with `asyncio.run`.

## Clients and repositories

- Place each infrastructure integration under `core/clients/<service>/`.
- Put connection creation, opening, closing, and FastAPI dependencies in
  `client.py`.
- `core/clients/__init__.py` opens and closes all clients through `open_clients`
  and `close_clients`.
- Keep PostgreSQL and Redis models and repositories inside their client
  packages.
- Use repositories for persistent data access. Features should not build
  database or Redis keys directly.
- Name models and repositories after the stored data, such as
  `RevokedAccessToken`, `RevokedAccessTokenRepository`, `RateLimit`, and
  `RateLimitRepository`.

## Core packages

- Put every reusable utility or cross-cutting capability in its own package
  under `core`, rather than in a standalone utility file.
- A core package owns its related helpers, middleware, errors, and configuration
  when they exist.
- Keep orchestration-only modules such as `lifespan.py` and `middlewares.py` as
  files. They coordinate packages and do not define a reusable capability.
- Keep focused application contracts and configuration, such as `errors.py` and
  `settings.py`, as files.
- `core/jobs` owns the Celery base task, the cancel and terminate helpers and the
  job errors; its Redis state is in `core/clients/redis`.
- `core/logging` owns logger configuration and request logging middleware.
- `core/security` owns JWT, passwords, public paths, access dependencies, security
  errors, and its middleware.
- `core/ratelimit` owns rate limit errors and middleware. Its persistent state
  belongs to the Redis models and repositories.
- `core/middlewares.py` only registers middleware in application order.
- `core/lifespan.py` opens and closes infrastructure clients.

## Import boundaries

`tests/test_boundaries.py` scans `src/` and fails with the file and the import:

- features never import each other; shared data goes through repositories;
- only `core/gemini` imports `gemini`, and only `gemini` or `gemini.errors`;
- only `api/v1/assistant/runs/adapters` imports the agent package, `geomind`, and only
  `geomind` or `geomind.<name>`;
- `tests/test_no_comments.py` tokenizes `src` and `tests` and fails on any comment
  other than a tool directive.

## gemini

- Only `core/gemini` imports gemini, and only through `import gemini as gm`
  (`gm.<name>`, `gm.errors.<name>`). gemini's internal paths are moving; never use them.
- Services never call gemini directly; they call `core/gemini`.
- There are no physics formulas in the backend.
- A plant is gemini's plant document (`gm.Plant.from_dict` / `to_dict`). The document
  has a header (`format`, `kind`, `name`) and no class path; gemini checks it and
  names every problem with a path. Older documents fail with `old_format`.
- Every gemini validation error on a plant becomes `422 plant_invalid` with
  `details.problems` (gemini's `path`, `code`, `message`) and a joined `details.message`.

## Plant versions

- `plant_versions` holds one row per saved plant, with `content` exactly as
  `to_dict()` writes it. Rows are never updated.
- One JSON per version, because gemini's format already holds dated parameters and tag
  bindings per module and gemini validates the whole file on load. A second, split
  format would have to follow gemini forever.
- Saving content equal to the latest version is `409 conflict`, so there are no empty
  versions. The unique `(project_id, number)` constraint settles concurrent saves;
  the loser retries once.

## Tables

One Alembic migration (`0006`) added the tables of the app; each has a model in
`core/clients/postgres/models/` and a base repository in `.../repositories/`. Feature
code uses the repository; it does not add tables or queries of its own.

| Table | Holds | List index |
|---|---|---|
| `case_versions`, `case_files` | gemini's case document per version (never updated, like `plant_versions`); file name, size and MinIO key per version | `(project_id, number)` unique |
| `chats`, `messages` | conversations; a message carries its `run_id` | `(project_id, created, id)`, `(chat_id, created, id)` |
| `runs` | status, loop, pending `request`, `error`, usage totals; the id is the run id geomind uses | `(project_id, created, id)`, `(project_id, status)`, `(chat_id, created)` |
| `run_events` | geomind's full `event.to_dict()` with `sequence`, `type`, `public` | `(run_id, sequence)` |
| `run_artifacts` | bytes or JSON per key, with both `run_id` and `chat_id` | `(run_id, key)`, `(chat_id, key, created)` |
| `chat_states` | the problem state, one row per version | `(chat_id, version)` unique |
| `studies`, `results` | a Celery job per study (settings, status, progress, `task_id`, `missing`, `error`); its result with a summary and gemini's content | `(project_id, created, id)`, `(project_id, status)`, `results.study_id` |
| `documents` | uploaded files, MinIO key, extracted `text`, `searchable` | `(project_id, created, id)` |
| `activity` | one line per change, with an optional `link_route` and `link_id` | `(project_id, created, id)` |

- Case and plant versions share `VersionRepository` (numbering, identical content is
  `409 conflict` with `details.latest`, one retry when two saves race).
- A study's result is found through `results.study_id`; `studies` has no result column.
- A run artifact save adds a row; the newest row for a key wins, per run
  (`newest_for_run`) or per chat (`newest_for_chat`), so the next message of a chat reads
  what the first run produced.
- Progress of a running study is in Redis, not in `progress_done`; the worker writes
  `progress_done` when the study ends.
- `tests/test_migrations.py` (marker `postgres`) upgrades, downgrades and runs
  `alembic check` on an empty database.

## Export and import

- An export is a zip of `project.json` and one `plant/<number>.json` per version.
- Import checks every version with `validate_content` before writing and writes in
  one transaction. One bad version refuses the import with `422 plant_invalid` and
  the file name in `details`; a bad archive is `422 validation_failed` on `file`.
- Archives with `..` or absolute paths, or above `PROJECT_IMPORT_MAX_BYTES` uploaded or
  unpacked, are refused. Only `project.json` and `plant/<number>.json` are read.
- Imported versions keep their number, note and creation time; the importer becomes
  their author. Legacy project zips are not accepted.

## Middleware

- Register middleware in `core/middlewares.py` through `include_middlewares`.
- Security middleware validates access tokens and checks revocation through the
  Redis repository.
- Rate limiting uses a Redis repository and identifies authenticated users by
  user ID and public requests by IP address.
- Middleware raises application errors; `ErrorMiddleware` creates error
  responses.
- `ErrorMiddleware` sits inside `CORSMiddleware` and `RequestLoggingMiddleware`, so
  error responses carry CORS headers and are logged with their status.

## Responses

- Do not construct `JSONResponse` directly.
- Endpoints return response schemas or `None` for responses without a body.
- Services and middleware raise application errors instead of creating error
  responses.
- `ErrorMiddleware` serializes application errors through `ErrorResponse`.
- Every error body is `{"error": {"code", "message", "details"}}`. Codes are stable
  and listed in `../docs/contracts.md`; messages may change.
- Request validation becomes `422 validation_failed` with
  `details = {"fields": {"<field>": "<message>"}}`.
- Lists return `core.pagination.page.Page` (`{"items", "next"}`) and take `?cursor=`
  and `?limit=` through `PageParams`.

## Access

- The security middleware only checks the token. Every route must also depend on
  `CurrentUser` (or `AdminUser`), which loads the user and refuses inactive ones and
  revoked tokens. `tests/test_route_guard.py` fails, naming the route, for any route
  that does not, unless its path is in `PUBLIC_PATHS` in `core/security/paths.py`.
  That list holds login, refresh and health, and the test pins it.
- Every route that takes a project id depends on `AccessibleProject`, which calls
  `core.security.access.require_project`. The owner or an admin may read and change a
  project; anyone else gets `404 project_not_found`, the same as a missing project.
  Sharing will change only that function.
- Changing a password or deactivating a user sets `tokens_valid_after`.
  `require_token_holder` refuses access and refresh tokens issued before it, so the
  user signs in again, including in the session that changed the password.
- Outside the development environment, settings refuse to load when
  `FIRST_ADMIN_PASSWORD` is the `.env.example` value or shorter than 12 characters, so
  neither the API nor the worker starts. An empty value is allowed and creates no admin.
- Users are deactivated, never deleted, so authorship stays valid.
- Access tokens last minutes; refresh tokens are single-use and rotate on refresh.
  Logout revokes the access token and its paired refresh token.
- Users are created by an admin only. There is no public signup.

## Errors

- All project-defined errors inherit from `core.errors.AppError` and set `code`.
- Keep shared HTTP application errors in `core/errors.py`: `ConflictError`,
  `ForbiddenError`, `NotFoundError`, `ValidationFailedError`, `CaseInvalidError`
  (`case_invalid`, 422, `details.problems`), `MissingInputsError` (`missing_inputs`, 422,
  `details.missing = [{path, message}]`) and `NotImplementedYetError` (`not_implemented`,
  501, `details.missing` = the gemini or geomind name that does not exist). A route whose
  part is missing raises `NotImplementedYetError`; it never fakes the answer.
- Define errors used by one area close to that area, such as
  `core/security/errors.py`, `core/ratelimit/errors.py`, or
  `core/clients/errors.py`.

Examples:

```text
system + health                 -> /api/v1/system/health
identity + authn + login        -> /api/v1/identity/authn/login
identity + me                   -> /api/v1/identity/me
```

## Project rules

- No comments inside code; docstrings only. Tool directives (`# noqa`) are allowed.
- Functions that read or write a format are `from_<format>` / `to_<format>`
  (`from_csv`, `to_json`, `from_dict`, `to_dict`). Do not add new `load_x`, `parse_x`,
  `export_x` or `serialize` for these; rename the old ones when their
  code is next touched (done for the plant wrapper: `from_dict`, `to_dict`).
- Folder names are one word, lower case, no underscores.
- English only in code, docs, messages and commits.
- Nesting at most 3 levels; functions about 40 lines; guard clauses.
- No default values for engineering or economic inputs, in schemas, services,
  settings or migrations. A missing value fails the request with a stable error.
  Technical settings (page size, timeouts) may have defaults.
- No competition-specific values (names, temperatures, prices, limits) in code,
  defaults or migrations. They may appear only in test fixtures named as examples.

## FastAPI

Sources: FastAPI docs (lifespan, SSE) and `zhanymkanov/fastapi-best-practices`.

- Use `lifespan` (`FastAPI(lifespan=...)`), never `on_event`. Passing `lifespan`
  disables `startup`/`shutdown` handlers. Lifespan does not run for mounted sub-apps.
- Shared state lives in clients opened by `open_clients` and reached through
  dependencies, not module globals.
- Declare dependencies with `Annotated` aliases and reuse them:

```python
CurrentUser = Annotated[User, Depends(current_user)]


@router.get("/me", response_model=schemas.User)
async def read_me(user: CurrentUser) -> schemas.User:
    return schemas.User.model_validate(user)
```

- Chain small dependencies; FastAPI caches a dependency once per request, so
  `AccessibleProject` may depend on `CurrentUser` without a second lookup.
- Use `async def` routes and dependencies only with non-blocking I/O. Wrap a blocking
  SDK call in `run_in_threadpool`. Never run CPU-bound work in a request.
- Every route sets `response_model` (or a return annotation), a `status_code`, and
  `responses` for documented errors. Hide the docs outside development.
- Use RESTful paths and one path-variable name per resource (`project_id`) so
  dependencies are reused across routers.
- Work longer than one request, or work that must not be lost, goes to Celery, not
  to `BackgroundTasks`. The request returns `202` with the job record.
- Do joins and aggregation in SQL, not in Python loops over lazy relations.
- Tests use an async `httpx` client with `ASGITransport` and `dependency_overrides`,
  not monkeypatching internals.
- Ruff is the only linter and formatter.

## Pydantic v2

- Use `model_config = ConfigDict(...)`, `field_validator`, `model_validator`,
  `model_dump`, `model_validate`, and `from_attributes=True` for ORM objects. The v1
  names (`Config`, `validator`, `dict()`, `orm_mode`, `parse_obj`) are banned.
- Validate with types and constraints first (`Field(gt=0)`, `StrEnum`, `EmailStr`);
  write a validator only for rules a type cannot say. Validators raise `ValueError`.
- Request and response schemas are separate classes. Responses never reuse a model
  that carries a password hash or token.
- Engineering and economic fields are required (`float`, not `float = 0.0`). Use
  `X | None` only when absent is a real state, never to hide a missing input.
- Forbid unknown fields on requests: `ConfigDict(extra="forbid")`.
- Settings use `pydantic-settings`; one small settings class per concern when
  `settings.py` grows.

## SQLAlchemy 2.0

- Declarative models use `Mapped[...]` and `mapped_column()`. Nullability follows the
  annotation (`Mapped[str | None]` is `NULL`); set `nullable=` only to override.

```python
class Project(Base):
    """A user's project."""

    __tablename__ = "project"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

- Use the 2.0 query style: `select(...)` with `await session.scalars(...)`, never
  `session.query`.
- One `AsyncSession` per request, from a dependency that yields it and closes it.
  Repositories receive the session; services never create one.
- Set `expire_on_commit=False` on the async session maker, and load relations
  explicitly (`selectinload`); lazy loading fails under asyncio.
- Commit once per use-case, in the service or the unit-of-work dependency, not inside
  repositories.
- Give the metadata a naming convention for indexes and constraints, so Alembic can
  drop and alter them by name.
- Table names are lower_snake_case and singular unless a table is already plural
  (`plant_versions`); time columns end in `_at` and are timezone-aware UTC.

## Alembic migrations

- One migration per change, named `NNNN_<slug>.py`, reversible (`downgrade` works).
- Autogenerate is a draft. Review every script: it misses renames (shown as drop and
  add), anonymous constraints, some enums, and sequences. Write renames by hand with
  `op.alter_column` / `op.rename_table`.
- Name every constraint and index.
- Migrations are static: no imports of application models or services, no settings
  reads, no data derived from engineering defaults or competition values.
- Separate schema changes from data backfills. For a new `NOT NULL` column: add it
  nullable, backfill, then set `NOT NULL`, in separate steps or migrations.
- Never edit a migration that has been merged; add a new one.
- Rows that are never updated (`plant_versions`) get no update paths in migrations.
- CI runs `alembic upgrade head`, then `downgrade base`, then `upgrade head` on an
  empty database.

## Celery tasks

Source: Celery docs, "Tasks".

- A task is idempotent: running it twice with the same arguments leaves the same
  result. Key it by a job id and check the job state first.
- Pass ids and small values, never ORM objects or large payloads. The task loads what
  it needs.
- Use `acks_late=True` only for idempotent tasks; a crashed worker then redelivers.
  Set `task_reject_on_worker_lost` deliberately, since a killed child is otherwise
  acknowledged.
- Retry only transient errors, with bounded backoff:

```python
@app.task(
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def run_job(self, job_id: str) -> None:
    """Run one job; safe to repeat."""
```

- Never retry validation or `plant_invalid` errors; mark the job failed with the
  stable error code.
- Each task sets a time limit (`soft_time_limit`, `time_limit`).
- Task state that the user sees lives in the job table, not in the Celery result
  backend.
- Task bodies call `services.py` functions; they hold no business logic. They open
  their own session and never reuse a request session.
- Tests run tasks eagerly or call the function directly; never a real broker.

## Events over SSE with Redis pub/sub

Sources: FastAPI "Server-Sent Events" (needs FastAPI 0.135 or later) and Redis
"Pub/sub".

- Workers publish progress to a Redis channel prefixed with the environment and the
  job id (`<env>:job:<job_id>`); the SSE route subscribes and streams.
- Redis pub/sub is at-most-once: a missed message is lost. So the job table is the
  truth, every event carries an `id`, and a new or reconnecting stream first sends the
  current state from the database, then live events. Use Redis Streams if replay is
  ever needed.
- SSE routes use `response_class=EventSourceResponse`, yield typed
  `ServerSentEvent` items, and honour `Last-Event-ID`.

```python
@router.get("/{job_id}/events", response_class=EventSourceResponse)
async def stream_events(job: AccessibleJob) -> AsyncIterable[ServerSentEvent]:
    async for event in services.follow_job(job):
        yield ServerSentEvent(data=event, event=event.kind, id=str(event.number))
```

- `Cache-Control: no-cache` and `X-Accel-Buffering: no` are built in; do not add them
  again. FastAPI's own keepalive fires only after 15 s of silence; `core/sse` sends its own
  heartbeat comment every `SSE_HEARTBEAT_SECONDS` (10), so the built-in one never fires.
- The stream ends with a terminal event (`done` or `failed`). Always unsubscribe and
  close the pub/sub object in `finally`, also on client disconnect.
- Use `core/sse` for every stream: workers publish `StreamEvent`s with `publish_event`
  (store first, then publish); a route yields `follow(redis, channel_name(kind, id),
  replay, after, final_types)` with `after` from the `last_event_id` dependency. `follow`
  subscribes to Redis first, yields `replay(after)` (the stored events with
  `sequence > after`; `after` is `-1` for a new stream), then live events, dropping
  any already sent by sequence, and ends after a final type (`run.finished`). An event
  without a sequence (`text.delta`) is live only and carries no `id`. The browser
  `EventSource` cannot send the bearer header; the frontend uses `fetch` with
  `Authorization` (`@microsoft/fetch-event-source`), which sends `Last-Event-ID` on retry.
- SSE routes depend on `CurrentUser` and the resource guard like any route.

## Structured errors

- Raise `AppError` subclasses with a stable `code`; the body is
  `{"error": {"code", "message", "details"}}`. Do not raise `HTTPException`.
- Codes are snake_case, never renamed, and listed in `../docs/contracts.md`.
  Messages may change; clients switch on the code.
- `details` is a JSON object, never a string. Validation uses
  `{"fields": {"<field>": "<message>"}}`.
- Errors in SSE streams are sent as a final `failed` event with the same
  `{"code", "message", "details"}` shape.
- A Celery task failure stores the code and details on the job.
- Do not leak stack traces, SQL, or secrets in `message` or `details`; log them.

## Checklist

- [ ] Feature sits in `src/api/v1/<domain>/<feature>/`; the route set is in
      `../docs/contracts.md` first.
- [ ] Route has `response_model`, status code, `responses`, `CurrentUser`, and
      `AccessibleProject` when it takes a project id.
- [ ] One use-case per function in `services.py`; queries only in repositories.
- [ ] Pydantic v2 names only; request and response schemas are separate.
- [ ] No default for any engineering or economic input; no competition value.
- [ ] Models use `Mapped` / `mapped_column`; one session per request; one commit per
      use-case.
- [ ] Migration reviewed by hand, named constraints, reversible, static.
- [ ] Long work runs in a Celery task that is idempotent, bounded, and retries only
      transient errors.
- [ ] SSE sends current state first, uses event ids, and closes pub/sub in `finally`.
- [ ] Errors are `AppError` with a stable code listed in the contracts.
- [ ] No comments in code; `from_`/`to_` naming; one-word folders; English only;
      nesting at most 3; functions about 40 lines.
- [ ] Tests: boundary test, route guard test, failing test first for a bug fix.

Code implementation rules live in [DEVELOPMENT.md](DEVELOPMENT.md). Read that file only for tasks that create, modify, review, or test code.
