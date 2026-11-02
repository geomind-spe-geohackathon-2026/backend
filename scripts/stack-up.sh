#!/usr/bin/env bash
set -euo pipefail

BACKEND="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$(cd "$BACKEND/../frontend" && pwd)"
STACK="$BACKEND/.tmp/stack"
COMPOSE=(docker compose -f "$BACKEND/compose.services.yml" --env-file "$BACKEND/.env.dev")
PYTHON="$BACKEND/.venv/bin/python"

cd "$BACKEND"
mkdir -p "$STACK"

make_env() {
  cp .env.dev.example .env.dev
  chmod 600 .env.dev
  local key value
  for key in JWT_SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD MINIO_ROOT_PASSWORD; do
    value="$(openssl rand -hex 24)"
    sed -i.bak "s|^$key=replace-me|$key=$value|" .env.dev
    case "$key" in
      POSTGRES_PASSWORD) sed -i.bak "s|^\(POSTGRES_URL=.*\):replace-me@|\1:$value@|" .env.dev ;;
      REDIS_PASSWORD) sed -i.bak "s|:replace-me@127.0.0.1:6379|:$value@127.0.0.1:6379|" .env.dev ;;
      MINIO_ROOT_PASSWORD) sed -i.bak "s|^MINIO_SECRET_KEY=replace-me|MINIO_SECRET_KEY=$value|" .env.dev ;;
    esac
  done
  rm -f .env.dev.bak
  if [ -f .env ]; then
    local existing
    existing="$(grep '^OPENROUTER_API_KEY=' .env | cut -d= -f2- || true)"
    if [ -n "$existing" ]; then
      sed -i.bak "s|^OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$existing|" .env.dev
      rm -f .env.dev.bak
    fi
  fi
  echo "created .env.dev"
}

[ -f .env.dev ] || make_env

set -a
. ./.env.dev
set +a

if [ -z "${ASSISTANT_LLM:-}" ]; then
  if [ -n "${OPENROUTER_API_KEY:-}" ]; then ASSISTANT_LLM=openrouter; else ASSISTANT_LLM=fake; fi
fi
export ASSISTANT_LLM

GEMINI_VERSION="$("$PYTHON" -c 'import gemini; print(gemini.__version__)')"
SANDBOX_IMAGE="gemini-sandbox:$GEMINI_VERSION"
GEMINI_SOURCE="${GEMINI_SOURCE:-$BACKEND/.tmp/snap/gemini-217625e}"

prepare_sandbox() {
  if docker image inspect "$SANDBOX_IMAGE" >/dev/null 2>&1; then return 0; fi
  if [ -f "$GEMINI_SOURCE/docker/sandbox.Dockerfile" ]; then
    echo "building $SANDBOX_IMAGE from $GEMINI_SOURCE"
    docker build -q -f "$GEMINI_SOURCE/docker/sandbox.Dockerfile" -t "$SANDBOX_IMAGE" "$GEMINI_SOURCE" >/dev/null
    return 0
  fi
  return 1
}

if [ -z "${ASSISTANT_SANDBOX:-}" ]; then
  if prepare_sandbox; then ASSISTANT_SANDBOX=docker; else ASSISTANT_SANDBOX=none; fi
fi
export ASSISTANT_SANDBOX

alive() { [ -f "$STACK/$1.pid" ] && kill -0 "$(cat "$STACK/$1.pid")" 2>/dev/null; }

port_free() {
  ! lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

check_port() {
  local port="$1" name="$2"
  if port_free "$port"; then return 0; fi
  echo "port $port ($name) is in use by something else; stop it or change the port in .env.dev" >&2
  exit 1
}

mine_running() {
  "${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -qx "$1"
}

mine_running postgres || check_port "$POSTGRES_PORT" postgres
mine_running redis || check_port "$REDIS_PORT" redis
mine_running minio || { check_port "$MINIO_PORT" minio; check_port "$MINIO_CONSOLE_PORT" "minio console"; }
alive api || check_port "$API_PORT" api
alive frontend || check_port "$FRONTEND_PORT" frontend

echo "starting services"
"${COMPOSE[@]}" up -d --wait

echo "migrating"
"$PYTHON" -m alembic upgrade head

start() {
  local name="$1"
  shift
  if alive "$name"; then echo "$name already running"; return 0; fi
  nohup "$@" >"$STACK/$name.log" 2>&1 &
  echo $! >"$STACK/$name.pid"
}

wait_http() {
  local url="$1" name="$2" attempt
  for attempt in $(seq 1 60); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then return 0; fi
    sleep 1
  done
  echo "$name did not answer at $url; see $STACK/$name.log" >&2
  exit 1
}

start api "$PYTHON" -m uvicorn src.fastapi:app --host 127.0.0.1 --port "$API_PORT"
wait_http "http://127.0.0.1:$API_PORT/api/v1/system/health" api

echo "seeding"
"$PYTHON" scripts/seed.py --url "http://127.0.0.1:$API_PORT"

FORKED_BY_MULTIPROCESSING=1 start worker "$PYTHON" -m celery -A src.celery:app worker --loglevel=INFO --concurrency=2

cd "$FRONTEND"
VITE_API_MODE=real VITE_PROXY_TARGET="http://127.0.0.1:$API_PORT" \
  start frontend npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort
wait_http "http://127.0.0.1:$FRONTEND_PORT/" frontend

echo
echo "app      http://localhost:$FRONTEND_PORT"
echo "api      http://127.0.0.1:$API_PORT/docs"
echo "login    $FIRST_ADMIN_EMAIL / $FIRST_ADMIN_PASSWORD"
echo "assistant $ASSISTANT_LLM, sandbox $ASSISTANT_SANDBOX ($SANDBOX_IMAGE)"
echo "logs     $STACK/*.log"
