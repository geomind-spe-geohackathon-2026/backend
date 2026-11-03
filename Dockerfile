FROM python:3.12-slim

ENV MALLOC_ARENA_MAX=2

WORKDIR /app/backend

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
