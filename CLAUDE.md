# CLAUDE.md — Project rules for Planly (planly-django)

## Skills

Always activate the `django` skill at the start of every session. Use `/django` or invoke it via the Skill tool before writing any Django code.

## Project overview

Django 6+ task management app modeled after Microsoft Planner. This is an interactive tutorial project for junior developers — every chapter produces both implementation code and a tutorial Markdown document in `docs/tutorial/`.

## Tooling

- **Python 3.14+** with **Django 6+** and **PostgreSQL**
- **uv** for package management (not pip, not poetry)
- **ruff** for linting and formatting
- **ty** for type checking
- **Docker** with multi-stage builds using `debian:trixie-slim` + uv-managed Python
- **docker compose watch** for development (not bind mounts)
- **django-storages[s3]** for production file storage (S3/S3-compatible)

## Code style

- Top-level imports only. Never use local/inline imports unless absolutely necessary to avoid circular imports.
- Use `os.environ.get()` with defaults in base settings; validate required vars in environment-specific settings.
- Apps live in `apps/` (on `sys.path`), imported as top-level modules: `from plans.models import Plan`.
- Test classes: `Test*` prefix (e.g., `TestSettings`). Test functions: `test_*` prefix.
- Follow ruff's configured rules (see `pyproject.toml`). Run `uv run ruff check` before suggesting commits.

## Testing

- TDD approach: write tests alongside or before implementation code, not as a separate step after.
- Use pytest + factory-boy. Config is in `pyproject.toml` under `[tool.pytest.ini_options]`.
- Test settings: `config.settings.test` (via `DJANGO_SETTINGS_MODULE`).

## Tutorial conventions

- Explain WHY for every technical choice — this doubles as a best practices guide.
- Specs go in `.claude/specs/`, not `docs/`.
- Tutorial chapters go in `docs/tutorial/`.

## Git

- Never run `git commit` or `git add`. Suggest a commit message and let the user commit manually.
- Never run destructive git commands (force push, reset --hard, etc.) without explicit approval.

## Project structure

```
apps/              # Django apps (core, accounts, plans, tasks, attachments, notifications)
config/            # Django project config (settings/, urls.py, wsgi.py)
  settings/
    base.py        # Shared settings, loads .env via python-dotenv
    development.py # DEBUG=True, debug toolbar, console email
    test.py        # Fast hashing, dummy backends, temp media
    production.py  # Security headers, S3 storage, gunicorn
docs/tutorial/     # Tutorial chapters (Markdown)
templates/         # Project-level templates
static/            # Project-level static files
```
