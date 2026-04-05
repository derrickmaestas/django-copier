# Chapter 3 — Testing Setup & Your First Test

## Goal

By the end of this chapter you'll have:
- pytest and pytest-django configured for your project
- Dedicated test settings (`config.settings.test`) tuned for speed and isolation
- Smoke tests that prove the pipeline works end-to-end
- An understanding of *why* each testing decision was made

---

## Why Test Early?

Many tutorials introduce testing late — after the models, views, and templates are already built. That teaches you to bolt tests on after the fact, which is how most untested codebases start.

We're taking a different approach: **test infrastructure goes in before the first model**. From this chapter forward, every feature starts with a failing test. This is test-driven development (TDD), and it has real benefits:

- **Catches mistakes immediately** — you find bugs seconds after writing the code, not days later in production.
- **Documents behavior** — tests describe what the code should do in a way that stays up-to-date (unlike comments).
- **Enables refactoring** — when you need to restructure code, tests tell you instantly if you broke something.
- **Builds confidence** — deploying is less stressful when you have a test suite backing you up.

---

## Why pytest Instead of Django's Test Runner?

Django ships with a test runner (`python manage.py test`) built on Python's `unittest`. It works, but pytest is the industry standard for Python testing. Here's why:

| Feature | `manage.py test` | pytest |
|---|---|---|
| Test discovery | Explicit: `TestCase` classes, `test_*` methods | Automatic: any `test_*.py` file, any `test_*` function |
| Assertions | `self.assertEqual(a, b)` | `assert a == b` — plain Python |
| Fixtures | `setUp` / `tearDown` methods | `@pytest.fixture` with dependency injection |
| Plugins | Limited | Hundreds: `pytest-django`, `factory-boy`, `pytest-cov`, etc. |
| Output | Basic | Rich diffs, short tracebacks, `-v` for detail |

The key win is **plain `assert` statements**. Compare:

```python
# unittest style — verbose, hard to read
self.assertEqual(task.title, "Buy groceries")
self.assertTrue(task.is_overdue)
self.assertIn(user, task.assignees.all())

# pytest style — reads like English
assert task.title == "Buy groceries"
assert task.is_overdue
assert user in task.assignees.all()
```

When an `assert` fails, pytest uses introspection to show you exactly what both sides evaluated to. You get better errors with less code.

---

## Step 1: Test Dependencies

We already added the test dependencies in Chapter 1's `pyproject.toml`:

```toml
[dependency-groups]
test = [
    "pytest",
    "pytest-django",
    "factory-boy",
    "coverage",
]
```

| Package | Purpose |
|---|---|
| `pytest` | Test runner — discovers and executes tests |
| `pytest-django` | Integrates pytest with Django — provides database access, client fixtures, settings override |
| `factory-boy` | Creates test data without fixtures files — we'll use this heavily starting in Chapter 4 |
| `coverage` | Measures which lines of code your tests actually exercise |

### Why dependency groups instead of extras?

uv's dependency groups (`[dependency-groups]`) keep dev/test/prod packages separated without polluting your main `[project.dependencies]`. When you deploy to production, `uv sync --no-dev` installs only what's needed — no pytest, no ruff, no debug toolbar in the production image.

---

## Step 2: pytest Configuration

All pytest config lives in `pyproject.toml` — no need for a separate `pytest.ini` or `setup.cfg`:

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--reuse-db --no-migrations -q --import-mode=importlib"
```

Let's break down each setting:

### `DJANGO_SETTINGS_MODULE`

This tells pytest-django which settings module to use. We point it directly at `config.settings.test` — our test-specific settings that override the base with faster, safer defaults.

### `python_files`, `python_classes`, `python_functions`

These control test discovery. pytest scans for files matching `test_*.py`, classes matching `Test*`, and functions matching `test_*`. This matches the standard Python testing convention.

### `addopts` — the flags that matter

| Flag | What it does | Why |
|---|---|---|
| `--reuse-db` | Reuses the test database between runs instead of recreating it | Saves 2-5 seconds per run. The DB is only rebuilt when you add `--create-db` or change models. |
| `--no-migrations` | Creates tables directly from model definitions instead of running migration files | Faster and avoids issues with incomplete migrations during development. |
| `-q` | Quiet output — just dots and a summary | Less noise. Use `-v` when you need detail on a failing test. |
| `--import-mode=importlib` | Uses Python's `importlib` for test discovery instead of path-based imports | Required when apps live inside a package (`apps/`) with an `__init__.py`. Without this, pytest can resolve modules differently than Django expects. |

---

## Step 3: Test Settings

The `config/settings/test.py` module inherits everything from `base.py` and overrides the settings that matter for testing:

```python
from config.settings.base import *  # noqa: F401, F403

DEBUG = False
SECRET_KEY = "insecure-test-key-do-not-use-in-production"  # noqa: S105

# ──────────────────────────────────────────────
# Fast password hashing — tests run 10x faster
# ──────────────────────────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ──────────────────────────────────────────────
# Email — capture, don't send
# ──────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ──────────────────────────────────────────────
# Caching — per-test isolation
# ──────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ──────────────────────────────────────────────
# Background Tasks — inspect without executing
# ──────────────────────────────────────────────
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.dummy.DummyBackend",
    }
}

# ──────────────────────────────────────────────
# Media — use temp directory for uploaded files
# ──────────────────────────────────────────────
import tempfile  # noqa: E402

MEDIA_ROOT = tempfile.mkdtemp()
```

### Why each override matters

**`DEBUG = False`** — Tests should run with the same `DEBUG` setting as production. Some Django behaviors change when `DEBUG=True` (error pages, query logging, template error handling). Testing with `DEBUG=False` catches issues that would only surface in production.

**`SECRET_KEY`** — A hardcoded key so tests don't depend on environment variables. The `# noqa: S105` comment tells ruff's security checker (bandit) that yes, we know this is a hardcoded secret, and that's intentional in test settings.

**`MD5PasswordHasher`** — Django defaults to PBKDF2 with 870,000 iterations for password hashing. That's great for security but terrible for test speed. Every `UserFactory` call, every login in a test, runs that hash. MD5 is insecure for production but makes tests ~10x faster. Since test data never leaves your machine, this is safe.

**`locmem.EmailBackend`** — Captures emails in memory instead of sending them. You can assert on `django.core.mail.outbox` in your tests to verify emails were sent with the right content.

**`LocMemCache`** — In-memory cache that's isolated per test. No external Redis dependency needed for tests.

**`DummyBackend` for tasks** — Django 6's background task system captures enqueued tasks without executing them. This lets you test that the right tasks were enqueued without side effects.

**`tempfile.mkdtemp()` for MEDIA_ROOT** — Uploaded files go to a temp directory that's cleaned up by the OS. This prevents test uploads from polluting your project directory.

---

## Step 4: Your First Smoke Tests

Create `apps/core/tests/test_settings.py`:

```python
from django.conf import settings
from django.test import TestCase


class TestSettings(TestCase):
    """Verify the test pipeline and critical settings."""

    def test_django_settings_loaded(self):
        assert settings.SETTINGS_MODULE == "config.settings.test"

    def test_custom_user_model_configured(self):
        assert settings.AUTH_USER_MODEL == "accounts.User"
```

These tests aren't testing application logic — they're testing the test pipeline itself:

1. **`test_django_settings_loaded`** — Are the *test* settings loaded, not development or production? `settings.SETTINGS_MODULE` is Django's internal attribute that records which module was loaded. If this fails, `DJANGO_SETTINGS_MODULE` in `pyproject.toml` isn't pointing to the right module.

2. **`test_custom_user_model_configured`** — Is `AUTH_USER_MODEL` pointing to our custom user? This catches a common mistake — if you forget to set this before the first migration, Django uses the built-in `User` model and switching later requires wiping the database.

### Why `TestCase` instead of plain functions?

pytest can run plain `test_*()` functions — you don't need classes. But `django.test.TestCase` provides database transaction rollback between tests, which we'll need as soon as we start testing models. Starting with `TestCase` now means we don't need to refactor later.

---

## Step 5: Run the Tests

Make sure Postgres is running (either in Docker or locally):

```bash
# Start just the database
docker compose -f compose.yaml -f compose.services.yaml up -d
```

Then run:

```bash
uv run pytest
```

You should see:

```
2 passed in 0.26s
```

If you want more detail:

```bash
uv run pytest -v
```

```
apps/core/tests/test_settings.py::TestSettings::test_django_settings_loaded PASSED
apps/core/tests/test_settings.py::TestSettings::test_custom_user_model_configured PASSED
```

### Troubleshooting

- **`KeyError: 'DJANGO_SECRET_KEY'`** — The `.env` file is missing or doesn't contain `DJANGO_SECRET_KEY`. Run `cp .env.example .env` to create it.

- **Connection refused on port 5432** — Postgres isn't running. Start it with `docker compose -f compose.yaml -f compose.services.yaml up -d`.

- **`FATAL: role "planly" does not exist`** — The Postgres container hasn't initialized yet. Check `docker compose logs db` and wait for the healthcheck to pass.

---

## Step 6: Coverage (Preview)

We've configured coverage in `pyproject.toml` but won't enforce it until we have real application code. Here's a preview of how it works:

```bash
uv run coverage run -m pytest
uv run coverage report
```

```toml
# Already in pyproject.toml
[tool.coverage.run]
source = ["apps/"]
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 85
show_missing = true
```

| Setting | Purpose |
|---|---|
| `source = ["apps/"]` | Only measure coverage for our code, not Django internals or third-party packages |
| `omit = ["*/migrations/*", "*/tests/*"]` | Don't count auto-generated migrations or test files themselves |
| `fail_under = 85` | CI fails if coverage drops below 85% — prevents coverage from silently eroding |
| `show_missing = true` | Shows which specific lines aren't covered — helps you write targeted tests |

---

## How the Settings Chain Works

Understanding how settings load is important for debugging. Here's the chain when pytest runs:

```
pytest starts
  → pytest-django reads DJANGO_SETTINGS_MODULE = "config.settings.test" from pyproject.toml
  → imports config.settings.test
    → imports config.settings.base (shared settings, loads .env via python-dotenv)
    → overrides: SECRET_KEY, PASSWORD_HASHERS, EMAIL_BACKEND, etc.
  → Django is ready, tests run
```

Each entry point specifies its settings module directly — `manage.py` defaults to `config.settings.local`, `wsgi.py` to `config.settings.production`, and pytest to `config.settings.test`. There's no router in `config/settings/__init__.py` (it's empty). This makes it unambiguous which settings are loaded in each context.

The key insight: `base.py` uses `os.environ.get("DJANGO_SECRET_KEY", "")` with an empty default and loads `.env` via python-dotenv. The test settings override `SECRET_KEY` with a hardcoded value, so the fallback default never reaches Django's security check. In production, `production.py` validates that `SECRET_KEY` is set to a real value.

---

## Checkpoint

Before moving on, verify:

- [ ] `uv run pytest` passes all 2 tests
- [ ] `uv run pytest -v` shows tests under `apps/core/tests/test_settings.py`
- [ ] `uv run ruff check apps/ config/` reports no lint errors

**Next:** [Chapter 4 — Core Models & Abstract Bases](04-core-models.md)
