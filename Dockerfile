FROM python:3.12-slim

ENV MALLOC_ARENA_MAX=2

WORKDIR /app/backend

COPY requirements.txt ./
COPY vendor ./vendor
RUN cd vendor && sha256sum -c SHA256SUMS
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
