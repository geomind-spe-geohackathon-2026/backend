# Implementation Conventions

## General rules

- Solve the requested task with the smallest clear implementation.
- Do not add abstractions, base classes, factories, configuration, or layers for hypothetical future needs.
- Prefer direct, readable code over clever or generic code.
- Keep functions focused, but do not split a short flow into unnecessary wrappers.
- Reuse an existing pattern before introducing a new one.
- Do not write comments inside code. Explanations go in docstrings. Tool directives
  such as `# noqa` are allowed.
- Use full-word names, nesting of at most three levels, about 40 lines per function
  at most, and guard clauses instead of nested conditions.
- Keep times timezone-aware; store and return them in UTC.
- Use four spaces only for real Python blocks and continuations required by the formatter. Do not add visual indentation.
- Keep code compatible with Ruff and the configured 88-character line length.

## Imports

- Order imports as standard library, third-party packages, then local modules.
- Inside a feature package, import sibling modules and qualify their members.
- Use `schemas.Credentials` and `services.login_user`, instead of importing many names from `schemas.py` or `services.py`.
- Direct symbol imports are fine for small, stable dependencies from `core` or third-party packages when qualification would add no clarity.
- Do not create re-export modules only to shorten imports.

Example:

```python
from src.api.v1.identity.authn import schemas, services


async def login(credentials: schemas.Credentials) -> schemas.TokenResponse:
    return await services.login_user(credentials)
```

## API implementation

- `router.py` defines paths, status codes, response models, and dependencies.
- `schemas.py` contains only request and response models.
- One function in `services.py` per use-case, named after it, such as
  `create_user`.
- `services.py` contains the feature workflow and coordinates repositories and security helpers.
- `tasks.py` defines Celery tasks and exposes its module in `TASK_MODULES`.
- Keep database queries in `core/clients/postgres/repositories`, not in routers
  or services.
- Keep Redis data access in `core/clients/redis/repositories`.
- Pass repositories into feature services instead of using storage clients
  directly.

## Clients

- Keep one infrastructure integration in each `core/clients/<service>` package.
- Use `create_<service>_client`, `open_<service>`, `close_<service>`, and
  `get_<service>` for client lifecycle and FastAPI dependencies.
- Add models and repositories only when a client stores application data.
- Put operations shared by repository children in a small `base.py`.

## Core concerns

- Create a package under `core` for each reusable utility or cross-cutting
  capability. Keep its helpers, middleware, errors, and configuration together.
- Do not add standalone `utils.py`, `helpers.py`, or similar catch-all files.
- Keep a core concern as a single file only when it solely coordinates other
  packages, such as `lifespan.py` or `middlewares.py`.
- Keep focused contracts and configuration such as `errors.py` and `settings.py`
  as files.
- Keep logger setup in `core/logging/logger.py` and request logging in
  `core/logging/middleware.py`.
- Keep JWT and authentication middleware code in `core/security`.
- Keep rate limit HTTP behavior in `core/ratelimit` and its Redis persistence
  in `core/clients/redis`.
- Register middleware only in `core/middlewares.py`.
- Keep application startup and shutdown in `core/lifespan.py`.

## Errors

- Every project-defined error inherits from `AppError`.
- Raise application errors from services and middleware. Let `ErrorMiddleware`
  create the HTTP response from `ErrorResponse`.
- Do not construct `JSONResponse` directly. Return a schema from endpoints or
  raise an application error.

## Validation

The virtual environment was moved once, so call its tools through the interpreter:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest -n auto
```

While working, run only the tests of the changed code and of what imports it. Run the
full fast suite before each commit.

The fast suite never uses the network. New API tests use the `client` fixture from
`tests/conftest.py`: the real application on in-memory SQLite and `fakeredis`. New
tests mirror the source tree: `tests/api/v1/<domain>/<feature>/test_<usecase>.py` and
`tests/core/<package>/test_<module>.py`.

The current tests needed no database, so SQLite in memory was added for tests of
repositories and routes, with portable column types (`UtcDateTime`, `JSON` with a
`JSONB` variant). Tests that need real PostgreSQL behavior carry the `postgres` marker.
The default `-m "not postgres"` skips them. To run them against the compose PostgreSQL:

```bash
POSTGRES_TEST_URL=postgresql+asyncpg://user:password@localhost:5432/test_database \
    .venv/bin/python -m pytest -m postgres --no-cov
```

These tests create and drop every table, so point them at a scratch database.

Write tests for behavior, security boundaries, and failure handling. Do not add tests that only repeat the implementation.

## Compose

`../infrastructure/compose.yml` is the source of truth for the whole stack. The backend
image needs `../gemini`, which compose passes as the `gemini` build context; the same
will apply to the agent package in B2. This folder's `compose.yml` deploys only the API
and the worker behind Traefik.
