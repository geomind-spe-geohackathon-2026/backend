# Geomind backend

FastAPI backend with Celery, PostgreSQL, Redis, Alembic, and infrastructure
clients.

Core logging, security, and rate limiting live in separate packages. HTTP
middleware registration is centralized in `src/core/middlewares.py`.

Project conventions are documented in
[docs/CONVENTIONS.md](docs/CONVENTIONS.md). Code implementation and structure
rules are in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Local setup

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
```

Run FastAPI and Celery in separate terminals:

```sh
python -m src.main --fastapi
python -m src.main --celery
```

`requirements.txt` installs gemini from `../gemini` in editable mode, so that repository
must sit next to this one.

Configure the placeholder values in `.env` before starting the services.

API documentation is available at `http://localhost/docs`; health checks
use `GET /api/v1/system/health`.

## Local stack

`compose.dev.yml` runs only the services (PostgreSQL 16, Redis 7, MinIO, bound to 127.0.0.1,
compose project `geomind-dev`, named volumes). The API, the Celery worker and the frontend run
on the host from `.venv`, so the sibling `../gemini` and `../geomind` installs are the ones used.

```sh
scripts/stack-up.sh           # create .env.dev if missing, services, migrate, seed, API, worker, frontend
scripts/stack-down.sh         # stop everything, keep the data
scripts/stack-down.sh --reset # also drop the volumes
```

`.env.dev` (git-ignored, generated from `.env.dev.example`) holds the settings. The app is
`http://localhost:5173`, the API `http://127.0.0.1:8000/docs`; sign in as `admin@example.com` /
`example-password`. The seed (`scripts/seed.py`, idempotent) adds one example project with one
value missing. The assistant uses OpenRouter only when `OPENROUTER_API_KEY` is set in
`.env.dev`; otherwise `ASSISTANT_LLM=fake` plays a scripted run. Logs and pids are in
`.tmp/stack/`. With the image `gemini-sandbox:<gemini version>` present (built from a gemini
checkout with `make sandbox-image`; stack-up builds it from `.tmp/snap` when missing) the stack
uses `ASSISTANT_SANDBOX=docker`.

## Database and checks

```sh
alembic upgrade head
POSTGRES_TEST_URL=postgresql+asyncpg://user:password@127.0.0.1:5432/scratch_db \
  .venv/bin/python -m pytest -m postgres --no-cov
alembic revision --autogenerate -m "describe change"
.venv/bin/python -m pytest -n auto
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

## Docker

This folder deploys the API and the worker from its own `compose.yml` and `.env.production`. The
image needs `../gemini` and `../geomind`, which compose passes as extra build contexts:

```sh
docker build --build-context gemini=../gemini --build-context geomind=../geomind -t geomind-backend .
```

PostgreSQL, Redis, MinIO, ChromaDB and InfluxDB come from `../infrastructure`, which
also runs Traefik. Create the external `geomind` and `traefik` networks, start those
services, configure `.env.production` with their passwords, then run. Keep it apart
from `.env`, which the tests read:

```sh
cp .env.example .env.production
docker compose config -q
docker compose up -d --build
```

Traefik routes `https://api.geomind.team` to the FastAPI container, which runs the
database migrations before it starts. Compose runs
FastAPI and Celery as separate services from the same image.
