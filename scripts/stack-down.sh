#!/usr/bin/env bash
set -euo pipefail

BACKEND="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK="$BACKEND/.tmp/stack"
COMPOSE=(docker compose -f "$BACKEND/compose.services.yml" --env-file "$BACKEND/.env.dev")

cd "$BACKEND"

stop() {
  local name="$1" pid
  [ -f "$STACK/$name.pid" ] || return 0
  pid="$(cat "$STACK/$name.pid")"
  if kill -0 "$pid" 2>/dev/null; then
    pkill -TERM -P "$pid" 2>/dev/null || true
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    pkill -KILL -P "$pid" 2>/dev/null || true
    kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f "$STACK/$name.pid"
  echo "stopped $name"
}

for name in frontend worker api; do stop "$name"; done

if [ ! -f .env.dev ]; then exit 0; fi

if [ "${1:-}" = "--reset" ]; then
  "${COMPOSE[@]}" down --volumes --remove-orphans
  echo "services stopped, volumes dropped"
else
  "${COMPOSE[@]}" down --remove-orphans
  echo "services stopped, data kept"
fi
