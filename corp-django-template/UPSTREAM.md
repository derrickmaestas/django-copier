# Upstream lineage

This template ports content from [cookiecutter-django](https://github.com/cookiecutter/cookiecutter-django) and grafts on conventions from [planly-django](../). Because the template engines differ (Copier here, Cookiecutter upstream), we cannot `git merge` from upstream — updates are translated manually.

## Pinned upstream

We mined cookiecutter-django at: **(record the SHA when you do the first port pass — the short SHA from `git -C cookiecutter-django rev-parse --short HEAD` plus the date)**

## What we ported from cookiecutter-django

The following ideas, layout choices, and prompt names came from upstream:

- `config/settings/{base,local,test,production}.py` split — the file naming and module split.
- `apps/` package layout for first-party apps.
- Custom-user-model wiring (we replaced upstream's `users/` with `apps/accounts/` and swapped fields for `employee_id`+Team+Membership).
- Multi-stage Dockerfile with separate `compose/local/django/` and `compose/production/django/` directories.
- Secure-by-default `production.py` block (HSTS, SSL redirect, `SECURE_*` headers).
- Prompt names where the question still applied: `project_name`, `project_slug`, `description`, `author_name`, `email`, `domain_name`, `timezone`, `postgresql_version`, `use_whitenoise`, `open_source_license`.
- The shape of `tests/test_cookiecutter_generation.py` (generate sample projects, run their tests in CI).

## Deviations from cookiecutter-django

These are intentional and should NOT be reverted when pulling new ideas from upstream:

| Area | Upstream | This template | Why |
|---|---|---|---|
| Engine | Cookiecutter | Copier | `copier update` lets generated projects pull template improvements |
| Package manager | pip + requirements/*.txt or pip-tools | uv + pyproject.toml | Astral tooling, faster installs, single source of truth |
| Linter / formatter | Black + isort + flake8 + pre-commit | Ruff (lint+format) + ty + lefthook | Single tool, faster, modern |
| Env vars | django-environ | python-dotenv + os.environ.get() | Matches Planly; less magic |
| Logging | Default Django logging | structlog (console in dev, JSON in prod) | Corporate log aggregator parses JSON |
| Background tasks | Celery + Redis | django.tasks (Django 6 built-in) | One fewer service to operate |
| Cache | Redis (default) | Postgres `db.DatabaseCache` (default) | One fewer service; swap to Redis when measured |
| Auth | django-allauth | mozilla-django-oidc OR corp-gateway middleware skeleton | Corporate environment is SSO-only |
| User model | username/email choice | `employee_id` PK + Team + Membership | Mandated by corporate identity model |
| Cloud provider | AWS / GCP / Azure / None | None or S3-compatible | Internal S3-compatible storage only |
| Mail provider | Anymail (multi-provider) | SMTP only | Corporate mail relay |
| Frontend | Bootstrap 5 + Compressor/Gulp/Webpack | HTMX + Tailwind v4 (standalone binary) | Server-rendered + minimal JS |
| Error tracking | Sentry option | None | Corporate observability is log aggregation |
| Local mail testing | Mailpit | Console email backend | Sufficient for dev |
| Async | ASGI option | Sync only | No current need |
| CI | GitHub Actions / GitLab / Travis | GitLab only | Corporate standard |
| Deploy target | Heroku option + Procfile | Self-hosted (no Heroku files) | Internal infrastructure |
| Frontend build | Compressor / Gulp / Webpack | None (HTMX vendored) | No JS toolchain needed |
| Editor configs | PyCharm / VS Code dotfiles | None | Editor configs are personal |
| Docker base | `python:X-slim-trixie` | `debian:trixie-slim` + uv-managed Python | Decouples OS from Python version, faster runtime, security patches faster |
| Project deviation `lefthook.yml` | absent (uses `.pre-commit-config.yaml`) | shipped | Planly references it but doesn't ship one — fix that here |

## Maintenance cadence

Quarterly review of cookiecutter-django commits since the pinned SHA. Check for:

- New Django release accommodations (security patches in settings, deprecation fixes).
- Improvements to the test harness or hooks.
- New always-on patterns we'd want to adopt.

Skip:

- Changes to features we dropped (Heroku, GitHub Actions, Mailpit, etc.).
- Engine-specific Cookiecutter improvements.
- Updates to provider-specific integrations we don't use.

When you pull something from upstream, update the pinned SHA above and add an entry to a "Pulled from upstream" section here documenting what changed.
