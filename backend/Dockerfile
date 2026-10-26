# syntax=docker/dockerfile:1
#
# InterviewOS backend image.
#
#   docker build -t interviewos-backend ./backend
#   docker run --rm -p 8000:8000 \
#     -e ENVIRONMENT=production \
#     -e SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
#     -e DATABASE_URL=postgresql+psycopg://user:password@host:5432/interviewos \
#     interviewos-backend
#
# On start the container applies pending Alembic migrations and then starts Uvicorn.
# Run ONE replica at a time (or run `alembic upgrade head` as a separate release step),
# because two containers migrating the same database at once can race.

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------- builder
# Dependencies are installed into a virtualenv here, so the final image carries
# no pip cache and no build leftovers.
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
# Copy only the requirements first so this layer is cached until they change.
COPY requirements.txt .
# Every dependency ships a prebuilt manylinux wheel (OR-Tools, psycopg[binary],
# pydantic-core), so no compiler or libpq-dev is needed.
RUN pip install -r requirements.txt

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime

# libgomp1: the OpenMP runtime that OR-Tools' CP-SAT solver links against for
# multi-worker search. psycopg[binary] bundles its own libpq, so libpq5 is not needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app
# .dockerignore keeps .env, virtualenvs and caches out of the image.
COPY --chown=app:app . /app

USER app
EXPOSE 8000

# /health is public and does not touch the database, so it reports "the process is up".
# start-period covers the migration step that runs before Uvicorn starts.
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8000') + '/health', timeout=4)"]

# `exec` replaces the shell with Uvicorn, so Uvicorn becomes PID 1 and receives SIGTERM directly.
# If the migration fails, the container exits non-zero instead of serving an unmigrated schema.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
