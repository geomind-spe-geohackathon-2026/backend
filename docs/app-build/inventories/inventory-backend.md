# Backend inventory (A1)

Static findings; pytest was not run by A1.

## src/ tree

src/__init__.py, fastapi.py (app, run), main.py (--fastapi | --celery), celery.py (Celery app, include=TASK_MODULES)
src/api/__init__.py (TASK_MODULES), src/api/v1/__init__.py (prefix /api/v1)
src/api/v1/system/{__init__.py, health/{router,schemas,services,tasks}.py}
src/api/v1/identity/__init__.py (prefix /identity)
  authn/{router,schemas,services,tasks}.py; me/{router,schemas,services,tasks}.py; users/{router,schemas,services}.py
src/api/v1/workspace/__init__.py (prefix /workspace), projects/{router,schemas,services}.py
src/core/: errors.py, lifespan.py, middlewares.py, settings.py
  clients/: errors.py
    chromadb/client.py, influxdb/client.py, minio/client.py, openrouter/client.py, redis/client.py, postgres/client.py
    postgres/models/{user,project,plant_version}.py; postgres/repositories/{base,user,project,plant_version}.py
    redis/models/{rate_limit,revoked_access_token}.py; redis/repositories/{base,rate_limit,revoked_access_token}.py
  gemini/{__init__,errors,plant}.py
  logging/{logger,middleware}.py; pagination/page.py; ratelimit/{middleware,errors}.py
  security/{access,bootstrap,emails,errors,jwt,middleware,passwords,paths,schemas}.py

## tests/ tree

tests/conftest.py, test_app.py, test_boundaries.py, test_identity.py, test_main.py, test_repositories.py, test_route_guard.py, test_security.py
tests/api/v1/identity/{authn,me,users}/..., tests/api/v1/workspace/projects/... with archives.py helper
tests/core/clients/{test_plant_version, test_plant_version_postgres (marker postgres)}
tests/core/gemini/test_plant; tests/core/pagination/test_page; tests/core/security/{test_access,test_bootstrap}; tests/core/test_errors, test_settings

## HTTP routes (all /api/v1)

GET /system/health (public); POST /identity/authn/login, /refresh (public), /logout (204); GET /identity/me; POST /identity/me/password (204, revokes tokens); GET, POST /identity/users; PATCH /identity/users/{user_id}; GET, POST /workspace/projects; POST /workspace/projects/import; GET, DELETE /workspace/projects/{project_id}; GET /workspace/projects/{project_id}/export. No plant routes.

## Models

users (id, email, name, role, password_hash, active, tokens_valid_after, created_at); projects (id, name, owner_id, created, updated); plant_versions (id, project_id, number, plant_type, content JSON, digest, note, author_id, created; unique project_id+number; never updated).
Redis: RateLimit, RevokedAccessToken (dataclasses, not tables).

## Alembic (head 0005)

0001 create_users; 0002 user_identity_fields; 0003 create_projects; 0004 create_plant_versions; 0005 user_tokens_valid_after.

## Settings (src/core/settings.py)

APP_NAME=geomind-backend; APP_ENV=development; APP_DEBUG; APP_LOG_LEVEL; APP_VERSION=0.1.0; APP_CORS_ORIGINS=["http://localhost:5173"]; JWT_SECRET_KEY required; JWT_ALGORITHM; JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30; JWT_REFRESH_TOKEN_EXPIRE_DAYS=14; FIRST_ADMIN_EMAIL, FIRST_ADMIN_PASSWORD (empty = no admin); POSTGRES_URL, POSTGRES_POOL_SIZE, POSTGRES_MAX_OVERFLOW; REDIS_URL; CELERY_BROKER_URL; RATE_LIMIT_REQUESTS=100; RATE_LIMIT_WINDOW_SECONDS=60; PROJECT_IMPORT_MAX_BYTES=100000000; MINIO_*; CHROMADB_URL; INFLUXDB_*; OPENROUTER_BASE_URL; OPENROUTER_API_KEY="".

## Tests

Command: `cd backend && .venv/bin/python -m pytest -n auto`. pyproject addopts: --cov=src --cov-branch -m "not postgres". Lint: `.venv/bin/python -m ruff check .`, `ruff format --check .`.
Fast suite needs no services: SQLite in-memory (aiosqlite, StaticPool) via the `client` fixture, app with lifespan skipped, fakeredis. Postgres tests need POSTGRES_TEST_URL, `-m postgres --no-cov`.
129 test functions, 126 without the postgres marker.

## Celery

src/celery.py: Celery(APP_NAME, broker=CELERY_BROKER_URL, include=TASK_MODULES), UTC, task_ignore_result=True. Start with `python -m src.main --celery`. No tasks exist: each tasks.py only sets TASK_MODULES = (__name__,).

## Gemini wrapper (src/core/gemini/)

errors.py: PlantInvalidError (422, plant_invalid). plant.py: resolve_plant_class, load_plant (reads content["plant_type"]), dump_plant, validate_content, example_plant.
../gemini uses FORMAT 2 with header {"format": 2, "kind": "plant", "name"} and no plant_type, so the wrapper rejects real gemini output today. test_plant.py asserts the old behaviour.

## Boundaries

tests/test_boundaries.py (AST): gemini imported only under src/core/gemini, only as gemini, gemini.errors or gemini.<name>; geomind only under src/api/v1/assistant/runs/adapters (does not exist yet); features under src/api/v1/<domain>/<feature> never import each other.
tests/test_route_guard.py: every route depends on CurrentUser unless in PUBLIC_API_PATHS = {login, refresh, health}.

## Differences from section 5.1

1. 126 fast tests, not about 130.
2. The plant wrapper is broken on format 2, not merely outdated.
3. Health tests are in tests/test_app.py; no tests/api/v1/system tree.
4. Celery has zero real tasks.
5. Venv links gemini to the missing /Users/sahand/Desktop/crust-team/gemini (installed as 1.0.3; ../gemini is 0.3.0); pyvenv.cfg and shebangs point at the old /Users/sahand/Desktop/swarmax path. Root ../.venv has no packages.
