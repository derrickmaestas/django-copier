# Chapter 1 — Project Setup from Scratch

## Goal

By the end of this chapter you'll have a fully structured Django 6 project with:
- A `config/` package with split settings for development, test, and production
- Six app stubs organized under `apps/`
- The Astral toolchain (uv, ruff, ty) configured
- A custom user model registered before the first migration

No database, no Docker, no tests yet — just a clean foundation to build on.

## Prerequisites

- Python 3.14+ installed
- [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Git installed
- A terminal you're comfortable with

---

## Step 1: Create the Project Folder and Initialize Git

```bash
mkdir planly-django && cd planly-django
git init
```

Every project starts as a git repo. Commit early, commit often — you can always rewrite history later, but you can't recover uncommitted work.

## Step 2: Initialize uv and Add Django

```bash
uv init --no-readme --python 3.14
uv add django psycopg[binary] django-extensions "django-storages[s3]"
```

### Why uv?

uv is a Python package manager from [Astral](https://astral.sh/) (the same team behind ruff). We chose it over pip and poetry for several reasons:

- **Speed** — uv resolves and installs dependencies 10-100x faster than pip. On a cold install of this project's dependencies, uv finishes in under 2 seconds.
- **Lockfile** — `uv.lock` pins every transitive dependency with hashes, giving you reproducible builds without a separate `pip freeze > requirements.txt` step.
- **Dependency groups** — uv supports `[dependency-groups]` in `pyproject.toml`, so you can separate dev, test, and production dependencies without maintaining multiple `requirements/*.txt` files.
- **Virtual environments** — uv creates and manages `.venv` automatically. No `python -m venv` or `source .venv/bin/activate` needed — `uv run` handles it.
- **One tool** — uv replaces pip, pip-tools, virtualenv, and pyenv in a single binary.

This gives you a `pyproject.toml` with your dependencies and a `uv.lock` lockfile. Both are committed to git.

## Step 3: Scaffold Django

```bash
uv run django-admin startproject config .
```

Two important choices here:

### Why `config` instead of `planly`?

Django's default `startproject planly` creates `planly/planly/` — a nested directory with the same name as the repo. This causes constant confusion: "which `planly` do I mean?" Using `config` makes the purpose of the directory obvious: it holds project configuration (settings, root URLs, WSGI/ASGI entry points). Your app code lives elsewhere.

### Why `.` (dot)?

The trailing `.` tells Django to create the project in the current directory instead of creating a nested subdirectory. Without it, you'd get `planly-django/config/config/` — one level too deep.

After this command, you have:
```
planly-django/
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py    ← we'll replace this
│   ├── urls.py
│   └── wsgi.py
├── manage.py
├── pyproject.toml
└── uv.lock
```

## Step 4: Create the `apps/` Directory

```bash
mkdir apps
touch apps/__init__.py
```

### Why group apps under `apps/`?

Grouping all first-party apps under `apps/` provides a clean separation from config, scripts, docs, and third-party code. It also makes imports visually distinct — `from plans.models import Plan` is obviously project code, not a third-party package.

To make this work, add `apps/` to the Python path in your settings. We'll do this in the next step when we set up split settings.

## Step 5: Create the App Stubs

```bash
cd apps
uv run django-admin startapp core
uv run django-admin startapp accounts
uv run django-admin startapp plans
uv run django-admin startapp tasks
uv run django-admin startapp attachments
uv run django-admin startapp notifications
cd ..
```

### Why these six apps?

Each app represents a distinct domain boundary:

| App | Models | Why it's separate |
|-----|--------|-------------------|
| `core` | Abstract bases only | Shared patterns (timestamps, ordering) — no database tables, no views, no URLs |
| `accounts` | User, Team, Membership | Auth and identity is standalone. Everything depends on it, but it depends on nothing else. |
| `plans` | Plan, Bucket | The top-level board. Buckets are columns within a plan. Tightly coupled to each other but separate from task logic. |
| `tasks` | Task, Assignment, ChecklistItem, Label, Comment | The richest domain. Most business logic lives here. |
| `attachments` | Attachment | File handling (upload, storage, validation) has its own concerns. Could be swapped out without breaking other apps. |
| `notifications` | Notification, NotificationPreference | Cross-cutting: triggered by events in other apps. Has its own delivery infrastructure. |

**The dependency graph flows one way:**
```
core (no dependencies)
  ↓
accounts (depends on core)
  ↓
plans (depends on accounts, core)
  ↓
tasks (depends on plans, accounts, core)
  ↓
attachments (depends on tasks)
notifications (depends on tasks, accounts)
```

This ordering matters — it determines the order we build things in the tutorial, and the order migrations run.

### Restructure the app stubs

Django's `startapp` creates a flat `tests.py` file. We want a `tests/` package for better organization:

```bash
for app in core accounts plans tasks attachments notifications; do
  rm -f apps/$app/tests.py
  mkdir -p apps/$app/tests
  touch apps/$app/tests/__init__.py
  touch apps/$app/tests/test_models.py
  touch apps/$app/tests/test_views.py
  touch apps/$app/tests/factories.py
done
```

Add the extra files each app needs:

```bash
# Apps with signals, background tasks, and templates
for app in accounts plans tasks notifications; do
  touch apps/$app/signals.py
  touch apps/$app/managers.py
  touch apps/$app/tasks.py
  mkdir -p apps/$app/templates/$app
done

# Core gets templatetags, context processors, middleware
touch apps/core/managers.py
touch apps/core/context_processors.py
touch apps/core/middleware.py
mkdir -p apps/core/templatetags
touch apps/core/templatetags/__init__.py
touch apps/core/templatetags/core_tags.py

# Attachments gets managers
touch apps/attachments/managers.py
```

## Step 6: Split Settings

Django generates a single `config/settings.py`. For any project beyond a toy, you want separate settings per environment. Delete the generated file and replace it with a package:

```bash
rm config/settings.py
mkdir config/settings
```

### `config/settings/__init__.py` — The Environment Router

```python
import os

env = os.environ.get("DJANGO_ENV", "development")

if env == "production":
    from config.settings.production import *  # noqa: F401, F403
elif env == "test":
    from config.settings.test import *  # noqa: F401, F403
else:
    from config.settings.development import *  # noqa: F401, F403
```

### Why this pattern?

- **One env var controls everything** — set `DJANGO_ENV=production` and the right settings load. No need to change `DJANGO_SETTINGS_MODULE`.
- **Defaults to development** — a developer cloning the repo gets dev settings without any configuration.
- **The `# noqa` comments** silence ruff's wildcard-import warnings. This is one of the few places where `import *` is the right choice — each environment module is designed to be the complete settings namespace.

### `config/settings/base.py` — Shared Settings

This is the largest file. Everything common across all environments lives here:

```python
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root
sys.path.insert(0, str(BASE_DIR / "apps"))

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

INSTALLED_APPS = [
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "django_extensions",
    "storages",
    # Planly apps
    "core",
    "accounts",
    "plans",
    "tasks",
    "attachments",
    "notifications",
]
```

Key decisions in `base.py`:

- **`sys.path.insert(0, str(BASE_DIR / "apps"))`** — This is what lets you write `from plans.models import Plan` instead of `from apps.plans.models import Plan`.
- **`os.environ["DJANGO_SECRET_KEY"]`** — Hard crash if the env var is missing. This is intentional — a missing secret key should fail loudly, not silently fall back to an insecure default.
- **`AUTH_USER_MODEL = "accounts.User"`** — Must be set before the first migration. Changing this later requires wiping the database and starting over.
- **`DATABASES` uses PostgreSQL** — No SQLite, even in development. Your dev database should match production to avoid surprises.

### Why `os.environ` instead of `django-environ`?

Third-party env libraries add convenience methods like type casting and URL parsing. But for a Postgres-only project like Planly, the standard library covers everything:

- `os.environ["KEY"]` for required values (crashes if missing — that's a feature)
- `os.environ.get("KEY", "default")` for optional values with sensible defaults
- `int()` for numeric casting, `.split(",")` for lists

One fewer dependency means one fewer thing to audit, version-pin, and keep updated.

### `config/settings/development.py`

```python
from config.settings.base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
```

Development settings are permissive: `DEBUG = True`, `ALLOWED_HOSTS = ["*"]`, emails print to console, caching uses local memory. The Django Debug Toolbar is added here — it's a dev-only dependency that shows SQL queries, template rendering time, and cache hits.

### `config/settings/test.py`

```python
from config.settings.base import *  # noqa: F401, F403

DEBUG = False
SECRET_KEY = "insecure-test-key-do-not-use-in-production"  # noqa: S105

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.dummy.DummyBackend",
    }
}
```

Test settings are optimized for speed:
- **MD5 password hasher** — bcrypt/argon2 are intentionally slow (that's the point for security). MD5 makes tests run ~10x faster.
- **DummyBackend for tasks** — Background tasks are captured but never executed. Tests can assert a task was enqueued without actually sending emails.
- **Hardcoded `SECRET_KEY`** — Tests don't need a real secret. The `# noqa: S105` tells ruff's security checker this is intentional.

### `config/settings/production.py`

Production settings lock everything down: `DEBUG = False`, HTTPS enforced, HSTS headers, secure cookies, whitenoise for static files, Redis for caching, real SMTP for email. We'll flesh this out in Chapter 17.

## Step 7: Configure the App Configs

Each app's `apps.py` needs explicit `name`, `label`, and `default_auto_field`:

```python
# apps/plans/apps.py
from django.apps import AppConfig


class PlansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plans"
    label = "plans"
    verbose_name = "Plans & Buckets"
```

### Why set `default_auto_field` explicitly?

Django 6 defaults to `BigAutoField`, but being explicit prevents surprises if this ever changes. It also silences the `WARNINGS` that Django emits when the field isn't set.

## Step 8: Create the Placeholder User Model

Since we set `AUTH_USER_MODEL = "accounts.User"`, Django won't start without a User model in the accounts app. We create a minimal placeholder now and expand it in Chapter 5:

```python
# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model — placeholder, will be expanded in Chapter 5."""

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.username
```

### Why define a custom user model if it's identical to the default?

Django's documentation strongly recommends this, and for good reason: if you later need to add fields to User (profile photo, job title, display name), you can do it with a simple migration. If you're using Django's built-in `User` model, you'd need to create a separate `Profile` model with a OneToOne relationship — or worse, try to swap `AUTH_USER_MODEL` after migrations exist, which is extremely painful.

**Rule of thumb:** Always create a custom user model before your first migration, even if it's just `class User(AbstractUser): pass`.

## Step 9: Configure Tooling in `pyproject.toml`

All tool configuration lives in one file:

```toml
[tool.ruff]
target-version = "py314"
line-length = 99

[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "W",     # pycodestyle warnings
    "F",     # pyflakes
    "I",     # isort (import sorting)
    "B",     # flake8-bugbear (common bugs)
    "C4",    # flake8-comprehensions
    "UP",    # pyupgrade (modernize syntax)
    "DJ",    # flake8-django (Django-specific)
    "S",     # flake8-bandit (security)
]
ignore = ["S101"]  # allow assert in tests

[tool.ruff.lint.isort]
known-first-party = [
    "core", "accounts", "plans", "tasks", "attachments", "notifications",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
addopts = "--reuse-db --no-migrations -q"

[tool.coverage.report]
fail_under = 85
```

### The Astral Stack: uv + ruff + ty

We use three tools from [Astral](https://astral.sh/), and there's a reason they come from the same team:

- **uv** — Package management (replaces pip, pip-tools, virtualenv)
- **ruff** — Linting and formatting (replaces flake8, isort, black, pyupgrade, bandit)
- **ty** — Type checking (replaces mypy, pyright)

Using a unified toolchain means consistent behavior, shared configuration in `pyproject.toml`, and no version conflicts between tools. Ruff alone replaces 5+ separate tools and runs orders of magnitude faster.

### Why 99-character line length?

The default 88 (black) or 79 (PEP 8) is too narrow for Django code with long queryset chains and template paths. 99 gives breathing room while still fitting two files side-by-side on a modern monitor.

### Why `--reuse-db --no-migrations` in pytest?

- **`--reuse-db`** — Keeps the test database between runs. First run creates it; subsequent runs reuse it. Saves 5-10 seconds per run.
- **`--no-migrations`** — Creates tables directly from model definitions instead of running the migration chain. Much faster, and you don't need migrations to be correct just to run tests.

## Step 10: Create Project-Level Directories

```bash
mkdir -p templates/partials static/css static/js static/img docs/tutorial locale scripts
```

- `templates/` — Project-level templates (base.html, error pages, partials)
- `static/` — Project-level CSS, JS, images
- `docs/tutorial/` — Where these tutorial chapters live
- `locale/` — Translation files (if needed later)
- `scripts/` — One-off scripts and data migration helpers

## Step 11: Create `.env.example` and `.gitignore`

`.env.example` documents every environment variable the project uses. It's committed to git. The actual `.env` is gitignored:

```bash
# .env.example — copy to .env and fill in real values
DJANGO_ENV=development
DJANGO_SECRET_KEY=change-me-to-a-random-string
DB_NAME=planly
DB_USER=planly
DB_PASSWORD=planly
DB_HOST=localhost
DB_PORT=5432
```

## Step 12: Verify

```bash
# Check Django can load all apps
DJANGO_ENV=test uv run python -c "import django; django.setup(); print('OK')"

# Check ruff passes
uv run ruff check apps/ config/

# Format everything
uv run ruff format apps/ config/
```

If all three pass, your project structure is solid.

## Checkpoint

Before moving on, verify:

- [ ] `uv run python -c "import django; django.setup()"` succeeds (with `DJANGO_ENV=test`)
- [ ] `uv run ruff check apps/ config/` reports no errors
- [ ] The project tree matches the structure shown at the top of this chapter
- [ ] `pyproject.toml` has dependency groups for dev, test, and prod
- [ ] `AUTH_USER_MODEL` is set to `"accounts.User"` in `base.py`
- [ ] `.env.example` exists with documented environment variables

**Next:** [Chapter 2 — Dev Environment with Docker](02-dev-environment-docker.md)
