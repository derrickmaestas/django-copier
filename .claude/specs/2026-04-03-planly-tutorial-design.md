# Planly Tutorial Design Spec

## Context

**Project name: `planly-django`**. Planly is a Django 6+ task management app modeled after Microsoft Planner. The tutorial starts from an empty folder — all project scaffolding, configuration, and code is built from scratch as part of the tutorial. The implementation spec (`django-spec.md`) serves as the architectural reference, but not everything is finalized. The goal is to build the entire app incrementally while producing a companion tutorial for junior developers at a company who are learning Django on the job.

## Audience

Junior developers with some programming experience, learning Django in a professional context. They understand basic development concepts but need guidance on Django-specific patterns and professional architecture decisions. No need to explain Python fundamentals or what a database is. Do need to explain Django models, views, the ORM, migrations, and project-specific conventions.

## Format

**Hybrid: written guide + code.** Each tutorial chapter lives as a Markdown file in `docs/tutorial/` and corresponds to a phase of development. Chapters reference the actual code being built. The code is committed sequentially with clear commit messages — the git log tells the development story.

## Structure: Layer-by-Layer with TDD

The tutorial uses a layer-by-layer approach — building one Django layer at a time across all apps. This lets junior developers see the same pattern repeated for each app, reinforcing learning through repetition. Tests are written first (TDD) starting from Chapter 3.

---

## Chapters

### Phase 1: Foundation

#### Chapter 1 — Project Setup from Scratch
**What:** Create the entire project structure from an empty folder. Initialize git, set up the Django project, and explain every decision.
**Covers:**
- Create the `planly-django/` repo folder, `git init`
- Install uv (the Astral package manager) — why uv over pip/poetry (speed, lockfiles, resolution)
- `uv init`, `uv add django` — set up `pyproject.toml` with dependency groups (dev, test, prod)
- `django-admin startproject config .` — why `config` not `planly`, why `.` for flat structure
- Restructure into the `apps/` directory pattern, add `sys.path` insertion in settings
- Create app stubs: `python manage.py startapp <name>` for core, accounts, plans, tasks, attachments, notifications — then move them into `apps/`
- Split settings: refactor the single `settings.py` into `config/settings/` package with `base.py`, `local.py`, `production.py`, `test.py` — each entry point sets `DJANGO_SETTINGS_MODULE` directly (no `__init__.py` router)
- `pyproject.toml`: configure ruff, ty, pytest, coverage (Astral stack: uv + ruff + ty)
- `.env.example` and `.gitignore`
- `manage.py`, `wsgi.py`, `asgi.py` pointing to `config.settings`
- App domain boundaries and dependency graph: core → accounts → plans → tasks → attachments → notifications
- First commit

**Key files created:** `config/settings/*.py`, `config/urls.py`, `config/wsgi.py`, `config/asgi.py`, `apps/*/apps.py`, `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `.gitignore`, `manage.py`

#### Chapter 2 — Dev Environment with Docker
**What:** Create the complete Docker-based development environment from scratch.
**Covers:**
- Why Docker for development: consistent environments, no "works on my machine"
- Multi-stage `Dockerfile` using `python:3.14-slim-trixie` base image (why slim-trixie per pythonspeed.com best practices): builder stage (uv for dependency install, compile deps with gcc/libpq-dev) and runtime stage (slim image, non-root user, collectstatic)
- Using uv inside Docker: `COPY --from=ghcr.io/astral-sh/uv` for fast, cached dependency installs
- `compose.yaml` — base service definitions (db: postgres:17, redis: redis:7-alpine) with healthchecks
- `compose.override.yaml` — development overrides: web service with compose watch, `runserver`, debug ports, `DJANGO_SETTINGS_MODULE=config.settings.local`; worker service for background tasks
- `compose.prod.yaml` — production overrides: gunicorn, no volume mounts, collected static, `DJANGO_SETTINGS_MODULE=config.settings.production`
- `.dockerignore` to keep images lean
- `cp .env.example .env` and configure for local Docker
- `docker compose up` to start Postgres + Redis + Django
- `docker compose exec web python manage.py migrate`
- `docker compose exec web python manage.py createsuperuser`
- Verify admin loads at `localhost:8000/admin/`

**Key files created:** `Dockerfile`, `compose.yaml`, `compose.override.yaml`, `compose.prod.yaml`, `.dockerignore`

#### Chapter 3 — Testing Setup & Your First Test
**What:** Configure the test pipeline and establish the TDD rhythm.
**Covers:**
- `uv add --group dev pytest-django factory-boy coverage` — dev dependency group
- `pytest-django` configuration in `pyproject.toml`
- Test settings: `config/settings/test.py` (fast hashing, DummyBackend, locmem email)
- `factory_boy` introduction — what factories are and why they beat fixtures
- Writing a trivial "smoke test" to prove the pipeline works
- The TDD cycle: Red → Green → Refactor
- Running `pytest`, reading output, understanding `--reuse-db` and `--no-migrations`
- Coverage basics: `pytest --cov=apps/ --cov-report=term-missing`

**Key files:** `pyproject.toml`, `config/settings/test.py`, `conftest.py`

### Phase 2: Data Layer (TDD)

Each chapter in this phase follows the pattern: explain the concept → write tests → write implementation → run tests green → refactor.

#### Chapter 4 — Core Abstract Models
**What:** Build the shared abstract base classes that all other models inherit from.
**Covers:**
- Abstract models (`class Meta: abstract = True`) — no database tables
- `TimeStampedModel`: `created_at` (`auto_now_add`) and `updated_at` (`auto_now`)
- `OrderedModel`: `position` field for drag-and-drop reordering
- Why these exist in `core` and not duplicated per app
- Testing abstract models (create a concrete test model)

**Key files:** `apps/core/models.py`, `apps/core/tests/test_models.py`

#### Chapter 5 — Accounts: Users & Teams
**What:** Custom user model, teams, and membership with roles.
**Covers:**
- Why a custom user model and why it must be set before the first migration
- `AbstractUser` vs `AbstractBaseUser` — when to use which
- `AUTH_USER_MODEL = "accounts.User"` in settings
- Custom `UserManager` for `create_user` / `create_superuser`
- `Team` and `Membership` (explicit M2M through model with roles)
- `TextChoices` for the `Role` enum
- `UniqueConstraint` vs `unique_together`
- `on_delete` strategies: `CASCADE` vs `PROTECT` and when to use each
- `__str__` methods
- First real migration: `python manage.py makemigrations accounts`
- Factories: `UserFactory`, `TeamFactory`, `MembershipFactory`
- Tests: user creation, team membership, constraint enforcement

**Key files:** `apps/accounts/models.py`, `apps/accounts/managers.py`, `apps/accounts/tests/factories.py`, `apps/accounts/tests/test_models.py`, `apps/accounts/migrations/`

#### Chapter 6 — Plans & Tasks: The Core Domain
**What:** Build the heart of the application — plans, buckets, tasks, and related models.
**Covers:**
- `Plan`: title, description, team FK, visibility choices, owner, `created_by`
- `Bucket`: belongs to Plan, inherits `OrderedModel`, deferred unique constraint on position
- `Task`: belongs to Bucket, priority/progress enums, due_date, fat model methods (`mark_complete()`, `is_overdue`)
- `Assignment`: M2M through linking Task to User
- `ChecklistItem`: belongs to Task, inherits `OrderedModel`, `is_completed` field
- `Label`: belongs to Plan (shared across tasks in a plan), M2M to Task
- `Comment`: belongs to Task, `created_by` FK to User
- Custom QuerySet as manager: `TaskQuerySet.as_manager()` with `.for_user()`, `.overdue()`, `.search()`
- `PlanQuerySet` with `.for_user()`, `.with_task_counts()`
- `null=True` vs `blank=True` decision matrix
- `related_name` conventions
- Composite and partial indexes
- Factories for all models
- Tests: model creation, fat model methods, queryset methods, constraint enforcement, ordering

**Key files:** `apps/plans/models.py`, `apps/plans/managers.py`, `apps/tasks/models.py`, `apps/tasks/managers.py`, factories and tests for both apps

#### Chapter 7 — Attachments & Notifications
**What:** Complete the model layer with file uploads and the notification system.
**Covers:**
- `Attachment`: belongs to Task, file field, `uploaded_by`, size validation against `PLANLY_MAX_ATTACHMENT_SIZE_MB`
- S3 / S3-compatible object storage for attachments via `django-storages[s3]`
- `STORAGES["default"]` backend: local filesystem in dev, S3Boto3Storage in production
- `AWS_S3_ENDPOINT_URL` for S3-compatible services (MinIO, DigitalOcean Spaces, etc.)
- `Notification`: generic notification model, `recipient` FK, `actor` FK, verb/description, `read` flag, content type / object ID for linking to source
- `NotificationPreference`: per-user notification settings
- `FileField` and `upload_to` callable patterns
- Application-specific settings (`PLANLY_*`) referenced from models
- Factories and tests for both apps
- Running the full migration set: `python manage.py migrate`

**Key files:** `apps/attachments/models.py`, `apps/notifications/models.py`, `config/settings/production.py` (S3 config), factories and tests for both

#### Chapter 8 — Admin & Data Exploration
**What:** Register all models in Django admin, use the shell and admin to verify the data layer.
**Covers:**
- `admin.py` for each app: `@admin.register`, `list_display`, `list_filter`, `search_fields`
- Inline admin classes (e.g., `BucketInline` on `PlanAdmin`, `ChecklistItemInline` on `TaskAdmin`)
- Using `django-extensions` `shell_plus` for interactive exploration
- Creating test data via admin and shell to validate relationships
- Verifying the full model layer works end-to-end before building views

**Key files:** `apps/*/admin.py`

### Phase 3: Server-Rendered App (TDD)

#### Chapter 9 — URL Routing & Views
**What:** Wire up URL patterns and build views for all apps.
**Covers:**
- Root URLconf: thin `config/urls.py` delegating to app URLs
- App URL namespacing: `app_name = "plans"`, `namespace="plans"` in `include()`
- URL naming conventions: hyphen-separated (`plan-board`, `task-detail`)
- Function-based views vs class-based views — when to use which
- `@login_required` decorator and `LoginRequiredMixin`
- `get_object_or_404` with prefetch/select_related
- Permission checks: can the current user access this plan/task?
- Redirect patterns after create/update/delete
- Testing views: `RequestFactory`, `Client`, status codes, redirects, context data

**Key files:** `config/urls.py`, `apps/*/urls.py`, `apps/*/views.py`, `apps/*/tests/test_views.py`

#### Chapter 10 — Forms & Validation
**What:** Django forms for all user input.
**Covers:**
- `ModelForm` basics: `Meta.model`, `Meta.fields`, `Meta.widgets`
- Custom `clean_*` methods and `clean()` for cross-field validation
- Form rendering in templates (manual rendering for HTMX compatibility)
- `TaskForm`, `CommentForm`, `ChecklistItemForm`, `BucketForm`
- User/team-scoped querysets on form fields (e.g., assignees limited to team members)
- `formset_factory` for batch operations (e.g., reordering checklist items)
- Testing form validation: valid data, invalid data, boundary conditions

**Key files:** `apps/*/forms.py`, `apps/*/tests/test_forms.py`

#### Chapter 11 — Templates & HTMX Frontend
**What:** Build the full server-rendered UI with HTMX enhancements.
**Covers:**
- `base.html`: template inheritance, block structure, static files, HTMX script
- Template namespacing: `plans/plan_board.html`, not `board.html`
- Django 6 template partials for reusable components
- HTMX integration:
  - CSRF token via `hx-headers` on `<body>`
  - `hx-get` / `hx-post` for partial page updates
  - Inline task editing
  - Live comment submission
  - Bucket drag-and-drop reordering
- `_navbar.html`, `_empty_state.html` partials
- Error pages: `404.html`, `500.html`
- CSP nonces in templates (`{{ csp_nonce }}`)
- `core/context_processors.py`: app-wide template context
- `core/templatetags/core_tags.py`: custom template tags/filters

**Key files:** `templates/base.html`, `templates/partials/`, `apps/*/templates/`, `apps/core/context_processors.py`, `apps/core/templatetags/core_tags.py`, `static/css/`, `static/js/`

#### Chapter 12 — Signals & Background Tasks
**What:** Event-driven behavior and async processing.
**Covers:**
- Signal handlers in `signals.py`, connected in `AppConfig.ready()`
- Why signals live outside `models.py`
- Plan signal: auto-create default "To Do" bucket on plan creation
- Task signal: notify assignees when a task is assigned
- Django 6 `django.tasks` framework:
  - `@task()` decorator
  - `.enqueue()` to dispatch
  - `ImmediateBackend` (dev), `DummyBackend` (test), `DatabaseBackend` (prod)
  - Queue prioritization in production
- `send_assignment_notification`, `send_daily_digest`, `process_attachment`
- Testing signals: verify they fire and enqueue the right tasks
- Testing background tasks: `DummyBackend` inspection (`default_task_backend.results`)

**Key files:** `apps/*/signals.py`, `apps/*/apps.py` (ready method), `apps/*/tasks.py`, `apps/*/tests/test_signals.py`

### Phase 4: API & Search (TDD)

#### Chapter 13 — REST API with Django REST Framework
**What:** Build the API layer alongside the server-rendered app.
**Covers:**
- API code in `api/` subpackages: `apps/tasks/api/serializers.py`, `views.py`, `urls.py`, `permissions.py`, `filters.py`
- URL versioning: `/api/v1/`
- `ModelSerializer` and nested serializers
- `ModelViewSet` and `Router` for standard CRUD
- Custom permissions: `IsTeamMember`, `IsTaskAssignee`
- Filtering with `django-filter`
- JWT auth via `djangorestframework-simplejwt`
- Schema docs with `drf-spectacular` at `/api/docs/`
- API testing: `APIClient`, status codes, serialization validation

**Key files:** `apps/*/api/`, `config/urls.py` (API URL inclusion)

**New dependencies (via uv add):** `djangorestframework`, `djangorestframework-simplejwt`, `drf-spectacular`, `django-filter`

#### Chapter 14 — Full-Text Search
**What:** Postgres-native full-text search across plans and tasks.
**Covers:**
- Tier 1 (Plans): `GeneratedField` with `SearchVector` — same-table, unweighted
- Tier 2 (Tasks): `django-pgtrigger` with weighted `SearchVectorField` — cross-table (task title + description + comment text)
- `SearchQuery`, `SearchRank` for ranked results
- Search views and API endpoints
- Testing search: index population, query matching, ranking

**Key files:** `apps/plans/models.py` (GeneratedField), `apps/tasks/models.py` (SearchVectorField), search views/serializers

**New dependencies (via uv add):** `django-pgtrigger`

### Phase 5: Best Practices & Production Readiness

#### Chapter 15 — Django Best Practices
**What:** A standalone reference chapter that consolidates and expands on the patterns, principles, and trade-offs used throughout the tutorial.
**Covers:**
- Project structure: why `config/`, why `apps/`, why split settings
- Model design: fat models, push constraints to the database, `null` vs `blank`, choices enums, `related_name` conventions
- Query discipline: always use `select_related`/`prefetch_related`, avoid N+1, test query counts
- Testing philosophy: TDD rhythm, factories over fixtures, what to test and what not to
- Security by default: Django's built-in protections, CSP, never trust user input at boundaries
- Signals vs. model methods: when each is appropriate
- Background tasks: when to go async, queue design
- API design: versioning, permissions, serializer boundaries
- Code quality: the Astral stack (uv + ruff + ty), why a unified toolchain matters, consistent naming
- Common anti-patterns and how to avoid them
- "Rules of thumb" summary — a quick-reference checklist for daily development

**Key files:** `docs/tutorial/15-best-practices.md`

#### Chapter 16 — Security Hardening
**What:** OWASP considerations and Django's security features.
**Covers:**
- Django's built-in protections: CSRF, XSS, SQL injection, clickjacking
- Content Security Policy (Django 6 native CSP): report-only → enforcement
- File upload validation: size limits, content type checking, filename sanitization
- Permission checks in views: ensuring users can only access their own data
- `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*`, secure cookies
- Rate limiting considerations

**Key files:** `config/settings/production.py`, view permission checks

#### Chapter 17 — Performance & Query Optimization
**What:** Making the app fast with proper query patterns.
**Covers:**
- `select_related` and `prefetch_related` — when and how
- `Prefetch` objects for filtered/annotated prefetches
- `only()` and `defer()` for partial loading
- `Meta.indexes`: composite indexes, partial indexes, naming conventions
- `assertNumQueries` in tests — preventing N+1 regressions
- Django Debug Toolbar for development profiling
- Annotation/aggregation patterns for dashboard queries (e.g., task counts per bucket)

**Key files:** views with queryset optimization, tests with `assertNumQueries`

#### Chapter 18 — Production Deployment
**What:** Ship it. (Builds on the `compose.prod.yaml` skeleton created in Chapter 2 — this chapter fills in the production-specific details.)
**Covers:**
- Production compose: finalize `compose.prod.yaml` with gunicorn, no volume mounts, `collectstatic`
- `gunicorn.conf.py` configuration
- Whitenoise for static file serving
- Sentry for error tracking
- Structlog for structured JSON logging
- The `db_worker` process for background tasks
- Environment variable management in production
- Health checks and monitoring basics

**Key files:** `compose.prod.yaml`, `gunicorn.conf.py`, `config/settings/production.py`

---

## File Organization

```
docs/
  tutorial/
    00-introduction.md
    01-project-orientation.md
    02-dev-environment-docker.md
    03-testing-setup.md
    04-core-abstract-models.md
    05-accounts-users-teams.md
    06-plans-tasks-core-domain.md
    07-attachments-notifications.md
    08-admin-data-exploration.md
    09-url-routing-views.md
    10-forms-validation.md
    11-templates-htmx.md
    12-signals-background-tasks.md
    13-rest-api-drf.md
    14-full-text-search.md
    15-best-practices.md
    16-security-hardening.md
    17-performance-optimization.md
    18-production-deployment.md
```

## Git Strategy

Sequential commits with clear messages. No tags or checkpoint branches. The git log tells the story. Each chapter's implementation is committed before moving to the next chapter.

## Implementation Order

Build order follows the dependency graph:
1. Foundation (chapters 1-3): orientation, Docker, testing setup
2. Data layer (chapters 4-7): core → accounts → plans/tasks → attachments/notifications
3. Admin checkpoint (chapter 8): verify the data layer
4. Server-rendered app (chapters 9-12): URLs/views → forms → templates/HTMX → signals/tasks
5. API & Search (chapters 13-14): DRF API → full-text search
6. Best practices & production (chapters 15-18): best practices → security → performance → deployment

## Conventions for Tutorial Chapters

- Each chapter starts with a **Goal** section explaining what the reader will build and learn
- Code is shown in the context of the file it belongs to, with the file path as a header
- **Every technical decision includes a "Why" explanation** — not just what to do, but the reasoning behind the choice. When alternatives exist, explain what was considered and why this option was picked. This teaches junior devs to think in trade-offs, not just follow recipes.
- Each chapter ends with a **Checkpoint** section: what to verify before moving on
- Tests are always written before implementation (TDD) starting from Chapter 4
- New Django/Python concepts are explained when first introduced, then referenced in later chapters
- The tutorial doubles as a best practices reference — patterns and principles are called out explicitly as they're introduced

## Verification Plan

After each phase:
- **Phase 1:** `docker compose up` works, `uv run pytest` runs (trivial test passes), admin loads
- **Phase 2:** All model tests pass, migrations run clean, admin shows all models with test data
- **Phase 3:** Full app is navigable in browser, HTMX interactions work, all view/form tests pass
- **Phase 4:** API endpoints return correct data, search returns relevant results, API tests pass
- **Phase 5:** Best practices chapter reviewed, `compose.prod.yaml` builds and runs, security headers present, `pytest --cov` ≥ 85%
