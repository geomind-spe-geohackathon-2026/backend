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
│   ├── __init__.py           # Root routers and jobs
│   └── v1/
│       ├── __init__.py       # Version routers and jobs
│       ├── system/           # Domain
│       │   ├── __init__.py   # Domain routers and jobs
│       │   └── health/       # Feature
│       │       ├── __init__.py
│       │       ├── router.py
│       │       ├── schemas.py
│       │       ├── services.py
│       │       └── jobs.py
│       └── identity/         # Domain
│           ├── __init__.py   # Domain routers and jobs
│           ├── authn/        # Feature
│           │   ├── __init__.py
│           │   ├── router.py
│           │   ├── schemas.py
│           │   ├── services.py
│           │   └── jobs.py
│           └── me/           # Feature
│               ├── __init__.py
│               ├── router.py
│               ├── schemas.py
│               ├── services.py
│               └── jobs.py
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
    ├── logging/
    │   ├── logger.py         # Logger configuration
    │   └── middleware.py     # Request logging middleware
    ├── ratelimit/
    │   ├── errors.py
    │   └── middleware.py
    ├── security/
    │   ├── errors.py
    │   ├── jwt.py
    │   ├── middleware.py
    │   ├── passwords.py
    │   └── paths.py
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
- Only features have standalone `router.py` and `jobs.py` files.
- API, version, and domain packages gather routers and jobs in `__init__.py`.
- Do not define feature endpoints directly in aggregation packages.

## Background jobs

- Each feature defines a `jobs.py` and exposes its module in `JOB_MODULES`.
- Domain, version, and API `__init__.py` files gather `JOB_MODULES` from below.
- `src/celery.py` configures Celery and includes all gathered job modules.
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
- `core/security` owns JWT, passwords, public paths, security errors, and its
  middleware.
- `core/ratelimit` owns rate limit errors and middleware. Its persistent state
  belongs to the Redis models and repositories.
- `core/middlewares.py` only registers middleware in application order.
- `core/lifespan.py` opens and closes infrastructure clients.

## Middleware

- Register middleware in `core/middlewares.py` through `include_middlewares`.
- Security middleware validates access tokens and checks revocation through the
  Redis repository.
- Rate limiting uses a Redis repository and identifies authenticated users by
  user ID and public requests by IP address.
- Middleware raises application errors; `ErrorMiddleware` creates error
  responses.

## Responses

- Do not construct `JSONResponse` directly.
- Endpoints return response schemas or `None` for responses without a body.
- Services and middleware raise application errors instead of creating error
  responses.
- `ErrorMiddleware` serializes application errors through `ErrorResponse`.

## Errors

- All project-defined errors inherit from `core.errors.AppError`.
- Keep shared HTTP application errors in `core/errors.py`.
- Define errors used by one area close to that area, such as
  `core/security/errors.py`, `core/ratelimit/errors.py`, or
  `core/clients/errors.py`.

Examples:

```text
system + health                 -> /api/v1/system/health
identity + authn + signup       -> /api/v1/identity/authn/signup
identity + me                   -> /api/v1/identity/me
```

Code implementation rules live in [DEVELOPMENT.md](DEVELOPMENT.md). Read that file only for tasks that create, modify, review, or test code.
