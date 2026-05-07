# Planly

A team task-management application modeled after Microsoft Planner — plans, buckets, tasks, assignments, comments, attachments, and notifications. Built on Django 6, PostgreSQL, HTMX, Tailwind v4, and a Django REST Framework API.

The codebase doubles as an interactive tutorial for junior developers: every architectural decision is documented in `docs/tutorial/`, including the *why* behind every dependency, settings choice, and design pattern.

---

## Quick start

```bash
# 1. Clone and copy the env template
git clone <repo-url> django-planner
cd django-planner
cp .env.example .env

# 2. Bring up the dev stack (Postgres + web + tailwind watcher + worker)
docker compose up -d

# 3. Migrate and create the admin
docker compose exec web uv run python manage.py migrate
docker compose exec web uv run python manage.py createsuperuser

# 4. Open the app
open http://localhost:8000/
```

Default dev login (after `createsuperuser`): whatever you set; the seed script in `docs/tutorial/11-templates-htmx.md` adds a couple of demo users (`employee_id=2`, password `planlydev`).

---

## What's in the box

| Layer | Stack |
|---|---|
| **Server-rendered UI** | Django CBVs/FBVs, HTMX-driven partials, Tailwind v4, `django-template-partials`, `django-tailwind-cli`, `django-crispy-forms` |
| **API** | DRF + `drf-spectacular` (Swagger UI at `/api/v1/docs/`); JWT + session auth side-by-side; `django-filter` |
| **Background tasks** | Django 6 `django.tasks` framework with `DatabaseBackend` in production |
| **Search** | Postgres FTS — `GeneratedField` for plans (Tier 1), `django-pgtrigger` for tasks with comment fan-out (Tier 2), unaccent + English stemming |
| **Storage** | S3-compatible via `django-storages[s3]` for production media; local disk in dev |
| **Auth** | Custom `User` keyed on `employee_id`; password-based by default; corporate OIDC SSO available as a swap (see Appendix A) |
| **Tooling** | `uv` for packaging, `ruff` for lint, `ty` for type-check, `pytest-django` + `factory-boy` for tests, `pytest-cov` with an 85% gate |
| **CI/CD** | `.gitlab-ci.yml` with lint, test, schema validation, deploy-check, and a manual deploy stage gated on `v*` tags |
| **Deploy** | Multi-stage Docker (`debian:trixie-slim` + uv-managed Python), Gunicorn, WhiteNoise, Postgres-backed cache, structlog JSON logging |

---

## Project layout

```
django-planner/
├── apps/                    # First-party Django apps (Python package)
│   ├── core/                # Abstract bases, search view, /health/, context processors
│   ├── accounts/            # Custom User keyed on employee_id, Team, Membership
│   ├── plans/               # Plan + Bucket + per-app api/ subpackage
│   ├── tasks/               # Task + Assignment + ChecklistItem + Label + Comment + signals + api/
│   ├── attachments/         # Attachment model, upload validators, HTMX upload/delete views
│   └── notifications/       # Notification model + django.tasks fan-out + api/
├── config/                  # Project package — settings/, urls.py, wsgi.py, asgi.py
│   └── settings/
│       ├── base.py          # Shared settings (INSTALLED_APPS, DRF, structlog config)
│       ├── local.py         # DEBUG=True, debug toolbar, console email
│       ├── test.py          # MD5 hashing, dummy task backend, temp MEDIA_ROOT
│       └── production.py    # Fail-fast env validation, strict CSP, CACHES via DB
├── templates/               # Project-level templates (base.html, partials, errors)
├── static/                  # Project-level static files (vendored HTMX, source.css)
├── docs/tutorial/           # 18 chapters + Appendix A
├── compose.yaml             # Base services (db)
├── compose.override.yaml    # Dev overrides (web + worker + tailwind watch)
├── compose.prod.yaml        # Production overrides (no exposed db port, healthcheck)
├── Dockerfile               # Multi-stage: builder → runtime (libpq5 + libmagic1)
├── gunicorn.conf.py         # Production WSGI config
├── .gitlab-ci.yml
├── pyproject.toml           # uv-managed deps, ruff/ty/pytest config
└── manage.py
```

---

## Common commands

All commands run inside the `web` container (or replace `docker compose exec web` with your local equivalent if you've installed `uv` on the host).

```bash
# Dev server (auto-reload)
docker compose up

# Tests
docker compose exec web uv run pytest                    # fast inner loop, no coverage
docker compose exec web uv run pytest --cov              # with coverage gate (fails under 85%)
docker compose exec web uv run pytest apps/plans -v      # one app, verbose

# Lint & format
docker compose exec web uv run ruff check .
docker compose exec web uv run ruff format .

# Type check
docker compose exec web uv run ty check

# Schema validation (drf-spectacular)
docker compose exec web uv run python manage.py spectacular --validate --fail-on-warn

# Migrations
docker compose exec web uv run python manage.py makemigrations
docker compose exec web uv run python manage.py migrate

# Open a Django shell
docker compose exec web uv run python manage.py shell

# Tailwind one-shot rebuild (the dev `tailwind` service watches automatically)
docker compose exec web uv run python manage.py tailwind build
```

---

## URLs you'll hit

| Path | Purpose |
|---|---|
| `/` | Landing page |
| `/plans/` | Plan list (logged in) |
| `/plans/<id>/` | Kanban board for one plan |
| `/tasks/<id>/` | Task detail with comments, checklist, assignees, attachments |
| `/search/` | Unified full-text search across plans and tasks |
| `/notifications/` | In-app notifications |
| `/admin/` (or env-overridden in prod) | Django admin |
| `/api/v1/docs/` | Swagger UI for the REST API |
| `/api/v1/schema/` | OpenAPI 3 schema (YAML/JSON) |
| `/health/` | Public liveness + DB-readiness probe |

---

## Documentation

The tutorial under `docs/tutorial/` is the primary documentation. Eighteen chapters take you from an empty folder to a deployed app:

| Phase | Chapters |
|---|---|
| 1. Foundation | [1 — Project setup](docs/tutorial/01-project-setup.md), [2 — Docker dev env](docs/tutorial/02-dev-environment-docker.md), [3 — Testing setup](docs/tutorial/03-testing-setup.md) |
| 2. Data layer | [4 — Core models](docs/tutorial/04-core-models.md), [5 — Accounts](docs/tutorial/05-accounts.md), [6 — Plans & tasks](docs/tutorial/06-plans-tasks.md), [7 — Attachments & notifications](docs/tutorial/07-attachments-notifications.md), [8 — Admin](docs/tutorial/08-admin-data-exploration.md) |
| 3. Server-rendered app | [9 — URL routing & views](docs/tutorial/09-url-routing-views.md), [10 — Forms](docs/tutorial/10-forms-validation.md), [11 — Templates & HTMX](docs/tutorial/11-templates-htmx.md), [12 — Signals & background tasks](docs/tutorial/12-signals-and-background-tasks.md) |
| 4. API & search | [13 — REST API](docs/tutorial/13-rest-api.md), [14 — Full-text search](docs/tutorial/14-full-text-search.md) |
| 5. Best practices & production | [15 — Best practices](docs/tutorial/15-django-best-practices.md), [16 — Security hardening](docs/tutorial/16-security-hardening.md), [17 — Performance](docs/tutorial/17-performance.md), [18 — Deployment](docs/tutorial/18-deployment.md) |
| Appendix | [A — Corporate SSO via OIDC](docs/tutorial/appendix-a-corporate-sso.md) |

If you want the design rationale for a specific decision, the chapter that introduces it is the place to look — every choice is explained alongside the code that implements it.

---

## Requirements

- **Python 3.14+** (the Docker image installs it via uv; no need for a host Python)
- **Docker** + **Docker Compose v2**
- **PostgreSQL 17** (provided by `compose.yaml`)

The Astral stack (`uv`, `ruff`, `ty`) is what you'll use locally if you prefer not to run inside Docker; install via `pip install uv` and then `uv sync --all-groups`.

---

## License

(Set this to your organization's standard. The tutorial is content; the code is yours.)
