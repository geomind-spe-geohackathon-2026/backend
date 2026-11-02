ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

ARG GEMINI_VERSION
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf pip install --no-cache-dir --disable-pip-version-check "gemini-geothermal-suite-open==${GEMINI_VERSION}"

RUN useradd --create-home --uid 1000 sandbox
USER sandbox
WORKDIR /home/sandbox
