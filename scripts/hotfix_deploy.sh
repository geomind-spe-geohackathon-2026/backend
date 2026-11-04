#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
WHEELS=.tmp/hotfix-wheels

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

git archive HEAD | sg docker -c "docker build -q -t geomind-backend:candidate -"
if compgen -G "$WHEELS/*.whl" > /dev/null; then
  echo "adding local wheels: $(ls $WHEELS)"
  sg docker -c "docker build -q -f Dockerfile.hotfix --build-arg BASE=geomind-backend:candidate -t geomind-backend:candidate $WHEELS"
fi

sg docker -c "docker tag geomind-backend:latest geomind-backend:prev"
sg docker -c "docker tag geomind-backend:candidate geomind-backend:latest && docker compose up -d --no-build fastapi celery"

for _ in $(seq 1 30); do
  health=$(curl -s https://api.geomind.team/api/v1/system/health || true)
  echo "$health" | grep -q "$(python3 -c 'import re;print(re.search(r"VERSION = \"(.+)\"", open("src/version.py").read()).group(1))')" && break
  sleep 3
done
echo "health: $health"
sg docker -c "docker exec geomind-celery python -c 'import geomind, gemini; print(\"geomind\", geomind.__version__, \"gemini\", gemini.__version__)'"
