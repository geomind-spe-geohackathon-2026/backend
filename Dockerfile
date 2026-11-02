FROM python:3.12-slim

WORKDIR /app/backend

COPY requirements.txt ./
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf pip install --no-cache-dir -r requirements.txt

COPY . .
