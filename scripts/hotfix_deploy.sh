#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

exec 9>/tmp/geomind-deploy.lock
echo "waiting for the deploy lock..."
flock 9

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "commit your changes first"; exit 1
fi
git fetch -q origin
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "HEAD is not origin/main: pull or push main first"; exit 1
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
sg docker -c "docker exec geomind-postgres sh -c 'pg_dump -U \$POSTGRES_USER -d \$POSTGRES_DB -Fc'" > "$HOME/geomind-backups/geomind-prod-$stamp.dump"

# Hotfix build: the backend, gemini and geomind all come from the local clones, from their
# committed and pushed HEAD (gemini: dev, geomind: main). No GitHub release or wheel is used.
for repo in gemini geomind; do
  dir=../$repo
  if [ -n "$(git -C "$dir" status --porcelain --untracked-files=no)" ]; then
    echo "$repo: commit your changes first"; exit 1
  fi
  git -C "$dir" fetch -q origin
  if [ "$(git -C "$dir" rev-parse HEAD)" != "$(git -C "$dir" rev-parse @{u})" ]; then
    echo "$repo: HEAD is not its pushed branch: pull or push first"; exit 1
  fi
done

git archive HEAD | sg docker -c "docker build -q -t geomind-backend:candidate -"
ctx=$(mktemp -d)
trap 'rm -rf "$ctx"' EXIT
for repo in gemini geomind; do
  mkdir "$ctx/$repo"
  git -C "../$repo" archive HEAD | tar -x -C "$ctx/$repo"
  echo "building $repo $(git -C "../$repo" log --oneline -1)"
done
sg docker -c "docker build -q -f Dockerfile.hotfix --build-arg BASE=geomind-backend:candidate -t geomind-backend:candidate $ctx"

sg docker -c "docker tag geomind-backend:latest geomind-backend:prev"
sg docker -c "docker tag geomind-backend:candidate geomind-backend:latest && docker compose up -d --no-build fastapi celery"

for _ in $(seq 1 30); do
  health=$(curl -s https://api.geomind.team/api/v1/system/health || true)
  echo "$health" | grep -q "$(python3 -c 'import re;print(re.search(r"VERSION = \"(.+)\"", open("src/version.py").read()).group(1))')" && break
  sleep 3
done
echo "health: $health"
sg docker -c "docker exec geomind-celery python -c 'import geomind, gemini; print(\"geomind\", geomind.__version__, \"gemini\", gemini.__version__)'"
