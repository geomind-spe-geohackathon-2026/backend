# Prompt: feature inventory of the legacy GEMINI Flask backend

You are working in `/Users/sahand/Desktop/crust-team/gemini-legacy`, the old GEMINI suite.
We will reimplement its backend ourselves, so we need a complete list of every feature the
Flask backend offers and exactly where each one is implemented.

## Rules

- Read-only task. Do not edit, move, format, install, commit or push anything inside
  `gemini-legacy`. Do not run the app or its tests.
- Backend only. Do not analyse templates, static JS/CSS or any frontend code, and do not report
  which frontend page calls a route.
- Write everything to `/Users/sahand/Desktop/crust-team/gemini-legacy-backend-analysis/`
  (outside the legacy folder): the result in `backend-features.md`, scratch in `scratch/`.
- If you use subagents, use lighter models (sonnet or haiku), not the main model.
- Every claim must cite a real path and line range (`path/to/file.py:120-158`). If you could not
  confirm something, mark it `UNVERIFIED` instead of guessing.
- Speak up at the end: list anything that looked important but you could not classify, any
  external service or secret the backend needs, and anything that blocks a reimplementation.

## Step 1: map the backend

1. List the tree (skip `.git`, `node_modules`, `venv`, caches, static assets, datasets).
2. Find the Flask entry points: `Flask(`, `create_app`, `app.run`, `Blueprint(`,
   `register_blueprint`, `wsgi`, `gunicorn`, `docker-compose`, `Dockerfile`, config files.
3. Record how the app starts, how blueprints are registered, config/env variables, and which
   database / cache / file storage / message queue it uses.

## Step 2: extract every route

Search for `@app.route`, `@<bp>.route`, `add_url_rule`, `MethodView`, `@socketio.on`,
`flask_restful`/`Resource`, and any API framework on top of Flask. For each endpoint record:

- HTTP method(s) and URL (with blueprint prefix resolved)
- handler function and its location (`file:line`)
- what it does in one sentence
- inputs (query, form, JSON body, files, URL params) and output (HTML template name, JSON shape,
  file download, redirect, stream)
- auth / permission needed (login_required, roles, decorators)
- what it calls underneath: services, models, GEMINI model/framework modules, DB tables,
  background jobs (follow the call chain until it reaches the real logic, cite that location too)

## Step 3: non-route features

Also list features that are not a single route:

- authentication, users, roles, sessions
- database models and migrations (table, fields, relations, file)
- background or scheduled jobs (celery, threads, APScheduler, cron), and what they compute
- data import / export, file uploads, report generation, plotting
- integrations: GEMINI model/framework calls, external APIs, InfluxDB/SQL/other stores,
  chat / LLM features (e.g. chatpopup)
- websocket / realtime updates
- CLI commands (`flask` commands, `click`), management scripts
- error handling, logging, config switches that change behaviour

## Step 4: write the result

Write `/Users/sahand/Desktop/crust-team/gemini-legacy-backend-analysis/backend-features.md` with:

1. **Overview**: how the backend starts, stack, storage, config/env vars, external services.
2. **Feature list grouped by domain** (e.g. auth, plants/assets, wells, reservoir, simulation,
   monitoring/data, dashboards, chat, admin). Each feature as a row in a table:
   `ID | Feature | Endpoint(s) or trigger | Entry point (file:line) | Real logic (file:line) |
   Inputs -> Outputs | Depends on | Notes`.
3. **Route index**: every route in one flat table (method, URL, handler file:line, feature ID),
   so we can check nothing was missed.
4. **Data model**: tables/models with fields and file locations.
5. **Dependency map**: which features depend on which GEMINI packages/modules.
6. **Dead or broken code**: routes/features that are unreachable, unused, stubbed or clearly
   broken, with evidence.
7. **Open questions and risks** for the reimplementation.

Before finishing, cross-check: the number of routes in the route index must equal the number
of route registrations you found by grep; report both numbers. Then reply with a short summary:
feature count per domain, route count, and the open questions.
