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
    │   └── plant.py          # load_plant, dump_plant, validate_content, example_plant
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
- only `api/v1/assistant/runs/adapters` imports the agent package, as `swarmax` or
  `geomind`.

## gemini

- Only `core/gemini` imports gemini, and only through `import gemini as gm`
  (`gm.<name>`, `gm.errors.<name>`). gemini's internal paths are moving; never use them.
- Services never call gemini directly; they call `core/gemini`.
- There are no physics formulas in the backend.
- A plant is a class in `gm.plants`. `plant_type` from stored or uploaded JSON is
  never imported: `resolve_plant_class` looks its class name up in `gm.plants.__all__`
  and requires the `gemini` package. Comparing only those two means versions saved
  before gemini moves a file still load.
- Every gemini error becomes `422 plant_invalid` with gemini's message in `details`.

## Plant versions

- `plant_versions` holds one row per saved plant, with `content` exactly as
  `to_dict()` writes it. Rows are never updated.
- One JSON per version, because gemini's format already holds dated parameters and tag
  bindings per module and gemini validates the whole file on load. A second, split
  format would have to follow gemini forever.
- Saving content equal to the latest version is `409 conflict`, so there are no empty
  versions. The unique `(project_id, number)` constraint settles concurrent saves;
  the loser retries once.

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
- Keep shared HTTP application errors in `core/errors.py`.
- Define errors used by one area close to that area, such as
  `core/security/errors.py`, `core/ratelimit/errors.py`, or
  `core/clients/errors.py`.

Examples:

```text
system + health                 -> /api/v1/system/health
identity + authn + login        -> /api/v1/identity/authn/login
identity + me                   -> /api/v1/identity/me
```

Code implementation rules live in [DEVELOPMENT.md](DEVELOPMENT.md). Read that file only for tasks that create, modify, review, or test code.
