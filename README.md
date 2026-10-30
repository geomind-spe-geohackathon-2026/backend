# Swarmax backend

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

## Database and checks

```sh
alembic upgrade head
alembic revision --autogenerate -m "describe change"
.venv/bin/python -m pytest -n auto
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

## Docker

`../infrastructure/compose.yml` is the source of truth for running the whole stack; see
[its README](../infrastructure/README.md). The image needs `../gemini`, which both
compose files pass as a second build context:

```sh
docker build --build-context gemini=../gemini -t swarmax-backend .
```

This folder's `compose.yml` only deploys the API and the worker behind Traefik. Create
the external `swarmax` and `traefik` networks, configure `.env`, then run:

```sh
docker compose config -q
docker compose up -d --build
```

Traefik routes `https://api.swarmax.xyz` to the FastAPI container. Compose runs
FastAPI and Celery as separate services from the same image.
