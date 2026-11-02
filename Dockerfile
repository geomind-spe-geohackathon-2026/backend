FROM python:3.12-slim

WORKDIR /app/backend

COPY --from=gemini pyproject.toml README.md LICENSE /app/gemini/
COPY --from=gemini gemini /app/gemini/gemini

COPY --from=geomind pyproject.toml AGENTS.md /app/geomind/
COPY --from=geomind geomind /app/geomind/geomind

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
