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

# Build-stage system dependencies:
# - gcc, libpq-dev: compile psycopg (C extension)
# - curl, ca-certificates: fetch the standalone tailwindcss binary
ARG TAILWIND_VERSION=v4.1.10
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc libpq-dev curl ca-certificates && \
    curl -fsSL -o /usr/local/bin/tailwindcss \
        "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64" && \
    chmod +x /usr/local/bin/tailwindcss && \
    rm -rf /var/lib/apt/lists/*

# Let uv manage the Python runtime
ENV UV_PYTHON_INSTALL_DIR=/python
RUN uv python install 3.14

# Dev builds install all groups; production builds pass --no-dev
ARG UV_INSTALL_ARGS="--no-dev"

# Install dependencies first (cached layer — changes less often than code)
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project $UV_INSTALL_ARGS

# Copy project and install it
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked $UV_INSTALL_ARGS

# Compile Tailwind CSS once at build time (production-ready output).
# In dev, override with `manage.py tailwind watch` for live rebuilds.
# DB_HOST is bogus because tailwind build doesn't touch the database — but
# the local settings module reads the env var at import time.
RUN DJANGO_SECRET_KEY=build DJANGO_SETTINGS_MODULE=config.settings.local \
    DB_HOST=__build_only__ \
    /app/.venv/bin/python manage.py tailwind build

# ─── Stage 2: Runtime ────────────────────────────────────────
FROM debian:trixie-slim

WORKDIR /app

# Runtime system dependencies:
# - libpq5: psycopg's C extension at runtime (no -dev, no compiler)
# - libmagic1: backing library for python-magic, used by the attachment
#   upload validators to sniff file content types; without it,
#   `import magic` raises ImportError at request time
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 libmagic1 && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --system planly && \
    useradd --system --gid planly --no-create-home planly

# Reuse the binary the build stage already fetched — no second download,
# no ca-certificates package needed at runtime. Devs can run
# `manage.py tailwind watch` from inside the running container.
COPY --from=builder /usr/local/bin/tailwindcss /usr/local/bin/tailwindcss

# Copy uv so dev/test can run `uv run` commands
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the Python runtime and virtual environment from builder
COPY --from=builder /python /python
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    UV_NO_CACHE=1

USER planly

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]
