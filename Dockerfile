# ─── Stage 1: Build ──────────────────────────────────────────
# We use debian:trixie-slim + uv-managed Python instead of the official
# python:3.14-slim-trixie image. This decouples the OS from the Python
# version, gets security patches faster, and is 10-17% faster at runtime
# (see pythonspeed.com). To use the official image instead, replace both
# FROM lines with `FROM python:3.14-slim-trixie` and remove the
# `uv python install` and `UV_PYTHON_INSTALL_DIR` lines.
FROM debian:trixie-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install system dependencies needed to compile psycopg (C extension)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Let uv manage the Python runtime
ENV UV_PYTHON_INSTALL_DIR=/python
RUN uv python install 3.14

# Install dependencies first (cached layer — changes less often than code)
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy project and install it
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ─── Stage 2: Runtime ────────────────────────────────────────
FROM debian:trixie-slim

WORKDIR /app

# Runtime system dependencies only (no compiler)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    addgroup --system planly && \
    adduser --system --ingroup planly planly

# Copy the Python runtime and virtual environment from builder
COPY --from=builder /python /python
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

USER planly

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]
