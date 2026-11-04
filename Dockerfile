FROM python:3.12-slim

ENV MALLOC_ARENA_MAX=2

# The docker CLI for geomind's run_python sandbox; the worker reaches the host daemon through
# the socket mounted in compose.yml (ASSISTANT_SANDBOX=docker).
COPY --from=docker:28-cli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /app/backend

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
