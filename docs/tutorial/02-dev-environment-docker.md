# Chapter 2 — Dev Environment with Docker

## Goal

By the end of this chapter you'll have:
- A multi-stage Dockerfile using uv-managed Python on Debian Trixie
- Three compose configurations: full containers with file watching (dev default), services-only, and production
- Postgres running in a container with healthchecks
- Django running and accessible at `localhost:8000`

---

## Why Docker for Development?

Docker solves "works on my machine." Every developer on the team gets the same Postgres version, the same system libraries — regardless of whether they're on macOS, Linux, or Windows. It also means a new developer can go from `git clone` to a running app with a single command.

## The Compose File Strategy

We use four compose files, each with a distinct role:

| File | Purpose | When to use |
|------|---------|-------------|
| `compose.yaml` | Base services (db) | Always loaded |
| `compose.override.yaml` | Dev: adds web + worker with file watching | Auto-loaded by `docker compose up` |
| `compose.services.yaml` | Services only — no web/worker containers | When running Django locally |
| `compose.prod.yaml` | Production: gunicorn, no volumes | Deployment |

### Why `compose.yaml` not `docker-compose.yml`?

Docker Compose V2 (the current version) uses `compose.yaml` as the default filename. The old `docker-compose.yml` still works but is the legacy convention. Similarly, the command is now `docker compose` (with a space) not `docker-compose` (with a hyphen).

### Why separate files instead of one big file with profiles?

Compose profiles (`--profile dev`) are an alternative, but separate files are more explicit. You can see exactly what differs between environments by diffing two files. Profiles hide differences inside conditionals, which is harder to reason about — especially for junior developers reading the config for the first time.

### How the override pattern works

When you run `docker compose up`, Compose automatically loads `compose.yaml` and `compose.override.yaml` (if it exists) and merges them. This means development is the zero-config default — no extra flags needed.

For other configurations, you specify files explicitly:
```bash
# Services only (run Django locally)
docker compose -f compose.yaml -f compose.services.yaml up

# Production
docker compose -f compose.yaml -f compose.prod.yaml up
```

---

## Step 1: The Dockerfile

```dockerfile
# ─── Stage 1: Build ──────────────────────────────────────────
FROM debian:trixie-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

ENV UV_PYTHON_INSTALL_DIR=/python
RUN uv python install 3.14

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ─── Stage 2: Runtime ────────────────────────────────────────
FROM debian:trixie-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    addgroup --system planly && \
    adduser --system --ingroup planly planly

COPY --from=builder /python /python
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

USER planly
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]
```

Let's break this down.

### Why multi-stage?

A single-stage Dockerfile that installs gcc, compiles C extensions, and then serves the app would be ~400MB+. Multi-stage builds let you compile in one stage (with gcc, libpq-dev, and other build tools) and copy only the result into a clean runtime stage. Our runtime image has no compiler, no build headers — just the Python runtime, the virtual environment, and `libpq5` (the PostgreSQL client library needed at runtime by psycopg).

### Why `debian:trixie-slim` instead of `python:3.14-slim-trixie`?

The official `python:3.14-slim-trixie` image comes with Python pre-installed by the Docker team. We use the base Debian image and let uv manage the Python runtime instead. Per [pythonspeed.com](https://pythonspeed.com/articles/base-image-python-docker-images/), this approach:

- **Decouples the OS from Python** — you can update Debian and Python independently
- **Gets security patches faster** — uv pulls from python-build-standalone, which ships patches before Docker's images are rebuilt
- **Runs 10-17% faster** — python-build-standalone builds use optimizations that the Docker official image doesn't

> **Want to use the official image instead?** Replace both `FROM debian:trixie-slim` lines with `FROM python:3.14-slim-trixie` and remove the `UV_PYTHON_INSTALL_DIR` and `uv python install` lines. Everything else stays the same.

### Why uv inside Docker?

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
```

This copies the uv binary directly from Astral's official image. No curl, no installer script, no network call during the build. It's a single static binary — fast and reproducible.

### The two-phase dependency install

```dockerfile
# Phase 1: install dependencies only (cached)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Phase 2: copy code and install the project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev
```

This is the most important optimization in the Dockerfile. Dependencies change rarely; your code changes constantly. By installing dependencies in a separate layer *before* copying your code, Docker caches the dependency layer. When you change a Python file, only the second `uv sync` runs — saving minutes on each build.

Key flags:
- `--locked` — uses `uv.lock` exactly, no resolution. Reproducible builds.
- `--no-install-project` — first pass installs only dependencies, not your code
- `--no-dev` — excludes dev/test dependencies from the production image
- `--mount=type=cache` — persists uv's download cache between builds

### Environment variables

```dockerfile
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
```

- `UV_COMPILE_BYTECODE=1` — pre-compiles `.py` to `.pyc` during install. Slightly slower build, but faster container startup (no compilation at runtime).
- `UV_LINK_MODE=copy` — copies files instead of hardlinking. Required when the cache mount and install target are on different filesystems.

### Non-root user

```dockerfile
RUN addgroup --system planly && \
    adduser --system --ingroup planly planly
# ...
USER planly
```

Never run your application as root inside a container. If an attacker exploits a vulnerability in your app, they get root access to everything the container can reach. Running as a dedicated non-root user limits the blast radius.

---

## Step 2: `compose.yaml` — Base Services

```yaml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: planly
      POSTGRES_USER: planly
      POSTGRES_PASSWORD: planly
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U planly"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

### Why healthchecks?

Without healthchecks, `depends_on` only waits for the container to *start*, not for the service inside to be *ready*. Postgres takes a second or two to initialize. If Django tries to connect before Postgres is accepting connections, it crashes. The `pg_isready` check ensures Postgres is actually ready before dependent services start.

### Why a named volume for pgdata?

`pgdata:/var/lib/postgresql/data` persists your database between `docker compose down` and `docker compose up`. Without it, you'd lose all data every time you restart. Named volumes survive container recreation — you only lose data if you explicitly run `docker compose down -v`.

### Why expose ports?

The `ports` mapping (`5432:5432`) lets you connect to Postgres from your host machine — useful for running Django locally against the containerized database, or for connecting with database tools like pgAdmin or TablePlus.

---

## Step 3: `compose.override.yaml` — Development

```yaml
services:
  web:
    build: .
    command: uv run manage.py runserver 0.0.0.0:8000
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.local
      DB_HOST: db
    depends_on:
      db:
        condition: service_healthy
    develop:
      watch:
        # Sync Python source — Django's runserver auto-reloads on change
        - action: sync
          path: ./apps
          target: /app/apps

        - action: sync
          path: ./config
          target: /app/config

        - action: sync
          path: ./templates
          target: /app/templates

        - action: sync
          path: ./static
          target: /app/static

        # Restart on config file changes (not picked up by auto-reload)
        - action: sync+restart
          path: ./.env
          target: /app/.env

        # Rebuild image when dependencies change
        - action: rebuild
          path: ./pyproject.toml

        - action: rebuild
          path: ./uv.lock

  worker:
    build: .
    command: uv run manage.py db_worker
    env_file: .env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.local
      DB_HOST: db
    depends_on:
      db:
        condition: service_healthy
    develop:
      watch:
        - action: sync
          path: ./apps
          target: /app/apps

        - action: sync
          path: ./config
          target: /app/config

        - action: sync+restart
          path: ./.env
          target: /app/.env

        - action: rebuild
          path: ./pyproject.toml

        - action: rebuild
          path: ./uv.lock
```

### Why override the CMD with `runserver`?

The Dockerfile's `CMD` runs gunicorn (for production). In development, we override it with Django's built-in `runserver`, which provides auto-reload when you save a file. The `0.0.0.0` bind address is required inside Docker — `127.0.0.1` (the default) would only accept connections from inside the container.

### Why `docker compose watch` instead of volume mounts?

The traditional approach is to bind-mount your project directory into the container (`volumes: [.:/app]`). This works but has real downsides:

- **Slow on macOS and Windows** — Docker translates every filesystem call between host and container, which adds noticeable latency. Large projects with many files (like node_modules) can make your IDE and container sluggish.
- **All-or-nothing** — a bind mount shares *everything*, including files the container doesn't need (`.git`, docs, IDE configs).
- **One direction** — changes inside the container (e.g., migrations generated by `makemigrations`) don't sync back cleanly.

`docker compose watch` (introduced in Compose 2.22) replaces bind mounts with explicit rules. It watches your host filesystem and pushes changes into the running container. You control exactly what gets synced, what triggers a restart, and what triggers a full rebuild.

### The three watch actions

| Action | When to use | What happens |
|---|---|---|
| `sync` | Source code changes | File is copied into the container. Django's `runserver` detects the change and auto-reloads. |
| `sync+restart` | Config file changes (`.env`) | File is copied in and the container restarts, since env vars aren't picked up by auto-reload. |
| `rebuild` | Dependency changes (`pyproject.toml`, `uv.lock`) | The entire image is rebuilt. This runs `uv sync` again to install the new dependencies. |

### Why `DB_HOST: db`?

Inside Docker's network, services refer to each other by service name. The Postgres container is named `db` in compose.yaml, so Django connects to `db:5432` instead of `localhost:5432`.

---

## Step 4: `compose.services.yaml` — Services Only

```yaml
# compose.services.yaml — services-only mode for local development
# Use when you prefer running Django locally:
#   docker compose -f compose.yaml -f compose.services.yaml up
#   uv run manage.py runserver   # in another terminal
```

This file exists as documentation. Since `compose.yaml` already defines db with an exposed port, running `docker compose -f compose.yaml -f compose.services.yaml up` starts only the infrastructure services. You then run Django on your host machine:

```bash
docker compose -f compose.yaml -f compose.services.yaml up -d
uv run manage.py runserver
```

### When to use this vs. the full container setup?

Use `compose.services.yaml` when:
- You want faster iteration (no container rebuild when dependencies change)
- You need to attach a debugger to Django
- Your IDE's features work better with a local Python process

Use the default (full containers) when:
- You want the exact same environment as other developers
- You don't want to maintain a local Python setup
- You're onboarding and just want things to work

---

## Step 5: `compose.prod.yaml` — Production

```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
      DB_HOST: db
    depends_on:
      db:
        condition: service_healthy

  worker:
    build: .
    command: python manage.py db_worker
    env_file: .env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
      DB_HOST: db
    depends_on:
      db:
        condition: service_healthy
```

Key differences from development:
- **No `command` override on web** — uses the Dockerfile's `CMD` (gunicorn)
- **No volume mounts** — the code is baked into the image at build time
- **`DJANGO_SETTINGS_MODULE: config.settings.production`** — explicitly selects the production settings module (security headers, HTTPS, S3 storage, real email). While `wsgi.py` already defaults to production, the worker uses `manage.py` which defaults to local — so this override is essential.

We'll flesh out the production configuration in Chapter 18.

---

## Step 6: `.dockerignore`

```
.git
.venv
__pycache__
*.pyc
.pytest_cache
.ruff_cache
htmlcov
.coverage
*.egg-info
staticfiles
media
.env
.claude
docs
```

### Why does this matter?

Every `COPY . /app` in the Dockerfile sends the entire build context to the Docker daemon. Without `.dockerignore`, that includes your `.venv` (hundreds of MB), `.git` history, and media uploads. The `.dockerignore` file works like `.gitignore` — it excludes files from the build context, making builds faster and images smaller.

The most important exclusion is `.venv` — your local virtual environment is built for your host OS and won't work inside the Linux container. The container creates its own via `uv sync`.

---

## Step 7: `gunicorn.conf.py`

```python
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 30
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
```

### Why a config file instead of CLI flags?

Gunicorn accepts configuration via CLI flags (`--workers 4 --bind 0.0.0.0:8000`), but a config file is easier to read, version control, and document. The `workers = cpu_count() * 2 + 1` formula is gunicorn's own recommendation for CPU-bound applications.

---

## Step 8: Getting It Running

1. Create your `.env` file:
   ```bash
   cp .env.example .env
   ```

2. Start everything with file watching:
   ```bash
   docker compose up --watch
   ```

   This loads `compose.yaml` + `compose.override.yaml` automatically. The `--watch` flag enables file syncing — when you edit a Python file, the change is pushed into the container and Django's `runserver` auto-reloads.

   > **Tip:** You can also run `docker compose watch` to start watching without streaming logs. Useful if you prefer to check logs separately with `docker compose logs -f web`.

3. In another terminal, run the initial migration and create a superuser:
   ```bash
   docker compose exec web uv run manage.py migrate
   docker compose exec web uv run manage.py createsuperuser
   ```

4. Open `http://localhost:8000/admin/` — you should see the Django admin login page.

### Troubleshooting

- **"port already in use"** — something else is using port 5432 or 8000. Stop the conflicting service or change the port mapping in compose.yaml.
- **"database does not exist"** — the Postgres container may not have initialized yet. Check `docker compose logs db` and wait for the healthcheck to pass.
- **Build fails on `uv sync`** — make sure `pyproject.toml` and `uv.lock` are committed and not in `.dockerignore`.

---

## Checkpoint

Before moving on, verify:

- [ ] `docker compose up --watch` starts db, web, and worker without errors
- [ ] `http://localhost:8000/admin/` shows the Django admin login
- [ ] Editing a Python file in `apps/` triggers an auto-reload in the web container
- [ ] `docker compose exec web uv run manage.py migrate` runs without errors
- [ ] `docker compose down` stops everything cleanly
- [ ] `docker compose up --watch` again reuses the database (data persists via pgdata volume)

**Next:** [Chapter 3 — Testing Setup & Your First Test](03-testing-setup.md)
