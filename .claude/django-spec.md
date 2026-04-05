
# Django Best Practices Guide

> **Django 6+ · Python 3.13+ · PostgreSQL**
>
> All examples in this guide are based on **Planly** — a Django implementation of a Microsoft Planner–style task management application. Planly supports plans (boards), buckets (columns), tasks with assignments, checklists, labels, comments, attachments, and real-time notifications.

## Table of Contents

1. [Project Structure & Layout](#1-project-structure--layout)
2. [Settings & Configuration](#2-settings--configuration)
3. [Models & Database](#3-models--database)
4. [Views & URL Routing](#4-views--url-routing)
5. [Forms & Validation](#5-forms--validation)
6. [Templates & Frontend](#6-templates--frontend)
7. [Testing](#7-testing)
8. [Security Hardening](#8-security-hardening)
9. [Performance & Query Optimization](#9-performance--query-optimization)
10. [Code Quality & Tooling](#10-code-quality--tooling)
11. [Deployment & DevOps](#11-deployment--devops)
12. [Docker & Docker Compose](#12-docker--docker-compose)
13. [REST APIs with Django REST Framework](#13-rest-apis-with-django-rest-framework)
14. [Full-Text Search](#14-full-text-search)


---

# 1. Project Structure & Layout



## Philosophy

A good project layout answers three questions instantly for any developer who opens the repo: *where does new code go?*, *where do I find existing code?*, and *what does this project do?* The structure below optimizes for those answers while staying compatible with Django's conventions and tooling.


## Reference Layout

```
planly/                         ← repo root
├── config/                     ← project-level Django package (the "settings root")
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py         ← imports from base, detects environment
│   │   ├── base.py             ← shared settings (installed apps, middleware, db, etc.)
│   │   ├── development.py      ← DEBUG=True, django-debug-toolbar, console email backend
│   │   ├── production.py       ← security headers, real email, caching, logging
│   │   └── test.py             ← fast password hasher, in-memory caching, etc.
│   ├── urls.py                 ← root URLconf — thin, delegates to app urls via include()
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/                       ← all first-party Django apps live here
│   ├── __init__.py
│   ├── accounts/               ← custom user model, auth, teams, membership
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── forms.py
│   │   ├── managers.py         ← custom UserManager
│   │   ├── models.py           ← User, Team, Membership
│   │   ├── urls.py
│   │   ├── views.py
│   │   ├── tasks.py            ← Django 6 background tasks (django.tasks)
│   │   ├── signals.py          ← keep signals out of models.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_models.py
│   │   │   ├── test_views.py
│   │   │   └── factories.py    ← UserFactory, TeamFactory, MembershipFactory
│   │   ├── templates/
│   │   │   └── accounts/       ← namespaced: <app_name>/<template>.html
│   │   │       ├── login.html
│   │   │       └── profile.html
│   │   └── migrations/
│   │       └── 0001_initial.py
│   │
│   ├── plans/                  ← plans (boards) and buckets (columns)
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py           ← Plan, Bucket
│   │   ├── managers.py         ← PlanQuerySet (with .for_user(), .with_task_counts())
│   │   ├── urls.py
│   │   ├── views.py
│   │   ├── signals.py          ← e.g. create default "To Do" bucket on plan creation
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_models.py
│   │   │   ├── test_views.py
│   │   │   └── factories.py    ← PlanFactory, BucketFactory
│   │   ├── templates/
│   │   │   └── plans/
│   │   │       ├── plan_board.html
│   │   │       └── plan_list.html
│   │   └── migrations/
│   │
│   ├── tasks/                  ← tasks, assignments, checklists, labels, comments
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py           ← Task, Assignment, ChecklistItem, Label, Comment
│   │   ├── managers.py         ← TaskQuerySet (with .overdue(), .by_priority())
│   │   ├── forms.py            ← TaskForm, CommentForm, ChecklistItemForm
│   │   ├── urls.py
│   │   ├── views.py
│   │   ├── tasks.py            ← background jobs: send_task_reminder, recur_tasks
│   │   ├── signals.py          ← e.g. notify assignees when task is updated
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_models.py
│   │   │   ├── test_views.py
│   │   │   ├── test_tasks.py   ← tests for background task functions
│   │   │   └── factories.py    ← TaskFactory, LabelFactory, CommentFactory, etc.
│   │   ├── templates/
│   │   │   └── tasks/
│   │   │       ├── task_card.html
│   │   │       └── task_detail.html
│   │   └── migrations/
│   │
│   ├── attachments/            ← file uploads on tasks
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py           ← Attachment (generic or FK to Task)
│   │   ├── urls.py
│   │   ├── views.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_models.py
│   │   │   └── factories.py    ← AttachmentFactory
│   │   └── migrations/
│   │
│   ├── notifications/          ← in-app and email notifications
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py           ← Notification, NotificationPreference
│   │   ├── tasks.py            ← send_notification_email, send_daily_digest
│   │   ├── urls.py
│   │   ├── views.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_models.py
│   │   │   └── factories.py    ← NotificationFactory
│   │   ├── templates/
│   │   │   └── notifications/
│   │   │       └── digest_email.html
│   │   └── migrations/
│   │
│   └── core/                   ← shared utilities, base models, template tags
│       ├── __init__.py
│       ├── models.py           ← TimeStampedModel, SoftDeleteModel, OrderedModel
│       ├── middleware.py        ← e.g. TeamContextMiddleware
│       ├── context_processors.py
│       └── templatetags/
│           └── core_tags.py
│
├── static/                     ← project-level static files (collected by collectstatic)
│   ├── css/
│   ├── js/                     ← drag-and-drop board JS, htmx, etc.
│   └── img/
│
├── templates/                  ← project-level templates (base layouts, error pages)
│   ├── base.html
│   ├── partials/               ← Django 6 template partials for reusable components
│   │   ├── _navbar.html
│   │   └── _empty_state.html
│   ├── 404.html
│   └── 500.html
│
├── locale/                     ← i18n translation files (if needed)
│
├── requirements/
│   ├── base.txt                ← django>=6.0, psycopg[binary], etc.
│   ├── development.txt         ← -r base.txt + debug-toolbar, factory-boy, etc.
│   ├── production.txt          ← -r base.txt + gunicorn, sentry-sdk, whitenoise, etc.
│   └── test.txt                ← -r base.txt + pytest-django, coverage, etc.
│
├── docs/                       ← project documentation, ADRs
│
├── scripts/                    ← one-off scripts, data migration helpers
│
├── manage.py
├── pyproject.toml              ← tool config (ruff, ty, pytest)
├── Dockerfile
├── docker-compose.yml
├── .env.example                ← documented env vars, never real secrets
└── README.md
```


## Key Decisions Explained

### Why `config/` instead of a project-named package?

Django's `startproject planly` creates `planly/planly/` — a nested directory with the same name as the repo. This causes confusion ("which `planly` do I mean?") and makes renaming painful. Using `config/` is a well-established convention that makes the purpose of the directory immediately obvious: it holds configuration. Your `manage.py` and `wsgi.py` point to `config.settings` and `config.urls`.

### Why an `apps/` directory?

Grouping all first-party apps under `apps/` provides a clean separation from config, scripts, docs, and third-party code. It also makes imports visually distinct — `from plans.models import Plan` is unambiguous about it being project code.

To make this work, add `apps/` to the Python path in `config/settings/base.py`:

```python
# config/settings/base.py
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root

# Add apps/ to the path so Django discovers apps as top-level modules
sys.path.insert(0, str(BASE_DIR / "apps"))
```

With this in place, your `INSTALLED_APPS` and imports stay clean:

```python
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

    # Planly apps — listed by app label, resolved via sys.path
    "core",
    "accounts",
    "plans",
    "tasks",
    "attachments",
    "notifications",
]
```

Each app's `apps.py` should set an explicit `label` and `name`:

```python
# apps/plans/apps.py
from django.apps import AppConfig


class PlansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plans"
    label = "plans"
    verbose_name = "Plans & Buckets"

    def ready(self):
        import plans.signals  # noqa: F401
```

### Why split settings?

A single `settings.py` that branches on `if DEBUG` grows into an unreadable mess. Split settings give you:

- **`base.py`** — everything shared (apps, middleware, database, templates, auth, i18n).
- **`development.py`** — imports `*` from base, then overrides for local work.
- **`production.py`** — imports `*` from base, then locks things down.
- **`test.py`** — imports `*` from base, then optimizes for speed.

The `__init__.py` selects the module based on `DJANGO_ENV`:

```python
# config/settings/__init__.py
import os

env = os.environ.get("DJANGO_ENV", "development")

if env == "production":
    from config.settings.production import *  # noqa: F401, F403
elif env == "test":
    from config.settings.test import *  # noqa: F401, F403
else:
    from config.settings.development import *  # noqa: F401, F403
```

Set `DJANGO_SETTINGS_MODULE=config.settings` in `manage.py`, `wsgi.py`, and `asgi.py`. The `__init__.py` handles the rest.

### Why `tests/` as a sub-package inside each app?

A single `tests.py` file doesn't scale. The `tasks` app alone needs tests for models (Task, Assignment, ChecklistItem, Label, Comment), views (board interactions, task CRUD, drag-and-drop reordering), forms, and background jobs. Keeping tests inside the app — with `test_models.py`, `test_views.py`, `test_tasks.py`, etc. — means tests live next to the code they exercise.

Place `factories.py` (factory_boy) alongside the test files so factories are co-located with the app they model:

```python
# apps/tasks/tests/factories.py
import factory
from factory.django import DjangoModelFactory

from accounts.tests.factories import UserFactory
from plans.tests.factories import BucketFactory
from tasks.models import Task, Label


class LabelFactory(DjangoModelFactory):
    class Meta:
        model = Label

    name = factory.Sequence(lambda n: f"Label {n}")
    color = "#3498db"


class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    title = factory.Sequence(lambda n: f"Task {n}")
    bucket = factory.SubFactory(BucketFactory)
    created_by = factory.SubFactory(UserFactory)
    priority = Task.Priority.MEDIUM
    progress = Task.Progress.NOT_STARTED
```

### Why a separate `tasks.py`?

Django 6 ships with a built-in background tasks framework (`django.tasks`). Keeping task definitions in a dedicated `tasks.py` per app (rather than scattering `@task` decorators through views or models) makes tasks discoverable and testable in isolation. This mirrors the established convention that Celery projects already follow.

Planly uses background tasks heavily — sending assignment notifications, emailing daily digests, processing recurring tasks, and generating plan status reports:

```python
# apps/tasks/tasks.py
from django.tasks import task


@task()
def send_assignment_notification(task_id: int, assignee_id: int) -> None:
    """Notify a user when they're assigned to a task."""
    from accounts.models import User
    from tasks.models import Task

    task_obj = Task.objects.select_related("bucket__plan").get(pk=task_id)
    assignee = User.objects.get(pk=assignee_id)
    assignee.email_user(
        subject=f"You've been assigned: {task_obj.title}",
        message=(
            f"You were assigned to '{task_obj.title}' "
            f"in plan '{task_obj.bucket.plan.title}'."
        ),
    )
```

```python
# apps/notifications/tasks.py
from django.tasks import task
from django.utils import timezone


@task()
def send_daily_digest(user_id: int) -> None:
    """Send a morning email summarizing overdue and due-today tasks."""
    from accounts.models import User
    from tasks.models import Task

    user = User.objects.get(pk=user_id)
    overdue = Task.objects.filter(
        assignments__user=user,
        due_date__lt=timezone.now().date(),
        progress__lt=Task.Progress.COMPLETED,
    )
    # ... build and send digest email
```


## How Planly's Domain Maps to Apps

Choosing the right app boundaries is one of the most impactful structural decisions. Here's why Planly is split the way it is:

| App | Models | Rationale |
|-----|--------|-----------|
| `accounts` | `User`, `Team`, `Membership` | Auth and team identity is a standalone domain. Every other app depends on it, but it depends on nothing else. |
| `plans` | `Plan`, `Bucket` | A plan is the top-level organizational unit (the Kanban board). Buckets are columns within a plan. These are tightly coupled to each other but separate from individual task logic. |
| `tasks` | `Task`, `Assignment`, `ChecklistItem`, `Label`, `Comment` | The richest domain. Tasks live in buckets, have assignees, checklists, labels, and comments. This is where most business logic lives. |
| `attachments` | `Attachment` | File handling (upload, storage, virus scanning) has its own concerns and could be swapped out independently. Kept separate to avoid bloating the `tasks` app with file I/O logic. |
| `notifications` | `Notification`, `NotificationPreference` | Cross-cutting: triggered by events in `tasks`, `plans`, and `accounts`. Has its own delivery infrastructure (email, in-app) and user preferences. |
| `core` | `TimeStampedModel`, `SoftDeleteModel`, `OrderedModel` | Shared abstract base classes and utilities. No database tables of its own. |


## Naming Conventions

| Thing | Convention | Planly Example |
|-------|-----------|----------------|
| App names | Short, lowercase, plural where natural | `accounts`, `plans`, `tasks`, `notifications` |
| Model classes | PascalCase, singular | `Plan`, `Bucket`, `Task`, `ChecklistItem` |
| Model fields | snake_case, no redundant prefixes | `title`, `due_date`, `created_at` — not `task_title` on a `Task` |
| FK / M2M fields | Named for the related concept | `bucket` (FK), `assignees` (M2M), `created_by` (FK to User) |
| URL names | namespaced with the app, hyphen-separated | `plans:plan-board`, `tasks:task-detail`, `tasks:task-reorder` |
| Template files | snake_case, nested under `<app_name>/` | `plans/plan_board.html`, `tasks/task_card.html` |
| Management commands | snake_case verbs | `recur_tasks`, `send_daily_digests`, `cleanup_attachments` |
| Settings constants | UPPER_SNAKE_CASE | `DATABASE_URL`, `MAX_ATTACHMENT_SIZE_MB` |
| Test files | `test_<module>.py` | `test_models.py`, `test_views.py`, `test_tasks.py` |
| Factories | `<Model>Factory` | `PlanFactory`, `BucketFactory`, `TaskFactory` |


## Template Namespacing

Always namespace templates to avoid collisions between apps. Both `plans` and `tasks` could reasonably have a `detail.html` — without namespacing, one silently shadows the other.

```
# WRONG — flat templates, collision risk
apps/plans/templates/board.html
apps/tasks/templates/detail.html

# RIGHT — namespaced under the app name
apps/plans/templates/plans/plan_board.html
apps/tasks/templates/tasks/task_detail.html
```

Reference in views:

```python
# apps/plans/views.py
def plan_board(request, plan_id):
    plan = get_object_or_404(
        Plan.objects.prefetch_related("buckets__tasks__assignees"),
        pk=plan_id,
    )
    return render(request, "plans/plan_board.html", {"plan": plan})
```


## Static Files Strategy

Project-wide assets (base CSS, board drag-and-drop JS, shared icons) live in the top-level `static/` directory. App-specific assets (if any) live in `apps/<app>/static/<app>/`. Configure `STATICFILES_DIRS` to include the project-level directory:

```python
# config/settings/base.py
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic target — gitignored
```

In production, run `collectstatic` in CI (not on deploy) and serve from a CDN or whitenoise.


## The `core` App

Every project accumulates shared code that doesn't belong to any single domain app. In Planly, both `Bucket` and `ChecklistItem` need ordered positioning (drag-and-drop reordering), and every model needs timestamps. The `core` app is the home for these shared abstractions.

```python
# apps/core/models.py
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base providing created_at and updated_at timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrderedModel(models.Model):
    """Abstract base for models that support drag-and-drop reordering."""
    position = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["position"]
```

Both `Bucket` and `ChecklistItem` inherit from `TimeStampedModel` and `OrderedModel`:

```python
# apps/plans/models.py
from core.models import OrderedModel, TimeStampedModel


class Bucket(TimeStampedModel, OrderedModel):
    plan = models.ForeignKey("plans.Plan", on_delete=models.CASCADE, related_name="buckets")
    title = models.CharField(max_length=255)

    class Meta(OrderedModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["plan", "position"], name="unique_bucket_position"),
        ]

    def __str__(self):
        return self.title
```

Rules for the `core` app: it should have **no models that produce database tables** (only abstract bases), **no views**, and **no URLs**. If it starts growing those, the code belongs in a domain app.


## When to Create a New App

A common mistake is cramming everything into one or two giant apps. Another common mistake is creating dozens of micro-apps that each have one model. Aim for the middle ground.

**Create a new app when** the domain concept has its own models, its own business logic, and could (in theory) be removed or replaced without rewriting everything else. In Planly, `attachments` is a good example — file upload, storage backends, and virus scanning are self-contained concerns. Ripping out attachments wouldn't break plans or tasks.

**Don't create a new app for** a single utility model, a set of template tags, or a feature that only modifies an existing app's behavior. For example, `Label` and `ChecklistItem` live inside the `tasks` app — they only make sense in the context of a task and have no independent behavior worth isolating.

A rough heuristic: if the app would have fewer than two models and no views of its own, it probably doesn't need to be a separate app.


## Signals: Keep Them Out of `models.py`

Define signal handlers in a dedicated `signals.py` file and connect them in the app's `ready()` method. This keeps `models.py` focused on data structure and avoids import-time side effects.

In Planly, when a new plan is created, we auto-generate a default "To Do" bucket so the board isn't empty:

```python
# apps/plans/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from plans.models import Bucket, Plan


@receiver(post_save, sender=Plan)
def create_default_bucket(sender, instance, created, **kwargs):
    if created:
        Bucket.objects.create(plan=instance, title="To Do", position=0)
```

And when a task is assigned, we notify the assignee via a background job:

```python
# apps/tasks/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from tasks.models import Assignment
from tasks.tasks import send_assignment_notification


@receiver(post_save, sender=Assignment)
def notify_assignee(sender, instance, created, **kwargs):
    if created:
        send_assignment_notification.enqueue(
            instance.task_id, instance.user_id
        )
```

```python
# apps/tasks/apps.py
from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tasks"
    label = "tasks"
    verbose_name = "Tasks & Assignments"

    def ready(self):
        import tasks.signals  # noqa: F401
```


## Root URLconf

Keep the root URLconf thin. It should only include app URL modules and serve as a table of contents:

```python
# config/urls.py
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("plans/", include("plans.urls", namespace="plans")),
    path("tasks/", include("tasks.urls", namespace="tasks")),
    path("attachments/", include("attachments.urls", namespace="attachments")),
    path("notifications/", include("notifications.urls", namespace="notifications")),
]
```


## Checklist for New Projects

1. **Start with `accounts`, `core`, `plans`, and `tasks`** — the minimum viable set for Planly. Add `notifications` and `attachments` when you're ready.
2. **Set `AUTH_USER_MODEL = "accounts.User"`** in `base.py` before the first migration — changing it later is extremely painful.
3. **Create `.env.example`** with every environment variable the project uses, documented with comments. Never commit `.env`.
4. **Set `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`** in `base.py` (Django 6 defaults to this, but be explicit).
5. **Configure `pyproject.toml`** for ruff, ty, and pytest from day one — retrofitting linting onto an existing codebase is miserable.
6. **Run `manage.py makemigrations` and commit the initial migration** for every app before writing any other code.
7. **Sketch your models on paper first** — in Planly, the relationships between Plan → Bucket → Task → Assignment/ChecklistItem/Comment form a clear hierarchy. Getting this right early prevents painful migrations later.
-e 

---

# 2. Settings & Configuration



## Philosophy

Settings should be boring. A developer cloning the repo for the first time should be able to run the project with nothing more than `cp .env.example .env` and `docker compose up`. Production secrets should never appear in version control, and the difference between environments should be obvious at a glance — not buried in `if DEBUG` branches scattered across a single file.


## Split Settings Module

As established in Section 1, Planly uses a `config/settings/` package with environment-specific modules. Here's the full implementation.

### `config/settings/__init__.py` — Environment Router

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

### `config/settings/base.py` — Shared Settings

This is the largest file. Everything that's common across all environments lives here. Below is Planly's `base.py`, annotated section by section.

```python
# config/settings/base.py
import os
import sys
from pathlib import Path

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root
sys.path.insert(0, str(BASE_DIR / "apps"))

# ──────────────────────────────────────────────
# Environment variables
# ──────────────────────────────────────────────
# We read env vars directly with os.environ / os.environ.get().
# No third-party library required — keep dependencies minimal.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# ──────────────────────────────────────────────
# Application definition
# ──────────────────────────────────────────────
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

    # Planly apps
    "core",
    "accounts",
    "plans",
    "tasks",
    "attachments",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ──────────────────────────────────────────────
# Database — PostgreSQL only
# ──────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "planly"),
        "USER": os.environ.get("DB_USER", "planly"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "600")),
        "OPTIONS": {
            "options": "-c default_transaction_isolation=read\\ committed",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/plans/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ──────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csp",   # Django 6 CSP nonces
                "core.context_processors.planly_context",    # app-wide context
            ],
        },
    },
]

# ──────────────────────────────────────────────
# Internationalization
# ──────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────
# Static & Media files
# ──────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ──────────────────────────────────────────────
# Background Tasks (Django 6)
# ──────────────────────────────────────────────
# Base sets ImmediateBackend — dev and prod override as needed.
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.immediate.ImmediateBackend",
    }
}

# ──────────────────────────────────────────────
# Planly-specific settings
# ──────────────────────────────────────────────
PLANLY_MAX_ATTACHMENT_SIZE_MB = int(os.environ.get("PLANLY_MAX_ATTACHMENT_SIZE_MB", "25"))
PLANLY_MAX_BUCKETS_PER_PLAN = int(os.environ.get("PLANLY_MAX_BUCKETS_PER_PLAN", "200"))
PLANLY_MAX_TASKS_PER_PLAN = int(os.environ.get("PLANLY_MAX_TASKS_PER_PLAN", "9000"))
```

### `config/settings/development.py` — Local Development

```python
# config/settings/development.py
from config.settings.base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# ──────────────────────────────────────────────
# Debug toolbar
# ──────────────────────────────────────────────
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

# ──────────────────────────────────────────────
# Email — print to console
# ──────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ──────────────────────────────────────────────
# Background Tasks — run synchronously in dev
# ──────────────────────────────────────────────
# ImmediateBackend (inherited from base) runs tasks inline.
# This means calling send_assignment_notification.enqueue() in a view
# will block until the email sends — acceptable for local dev.

# ──────────────────────────────────────────────
# Caching — local memory for dev
# ──────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ──────────────────────────────────────────────
# Logging — verbose in dev
# ──────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.db.backends": {
            "level": "WARNING",  # set to DEBUG to see every SQL query
            "handlers": ["console"],
        },
        "planly": {
            "level": "DEBUG",
            "handlers": ["console"],
        },
    },
}
```

### `config/settings/production.py` — Locked Down

```python
# config/settings/production.py
from config.settings.base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")  # noqa: F405

# ──────────────────────────────────────────────
# Security
# ──────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ──────────────────────────────────────────────
# Content Security Policy (Django 6)
# ──────────────────────────────────────────────
from django.utils.csp import CSP  # noqa: E402

MIDDLEWARE.insert(  # noqa: F405
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,  # noqa: F405
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
)

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF, CSP.NONCE],
    "img-src": [CSP.SELF, "data:", "https:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
}

# Start in report-only mode while rolling out, then switch to SECURE_CSP
# SECURE_CSP_REPORT_ONLY = { ... }

# ──────────────────────────────────────────────
# Static files — whitenoise
# ──────────────────────────────────────────────
MIDDLEWARE.insert(  # noqa: F405
    MIDDLEWARE.index("django.contrib.sessions.middleware.SessionMiddleware"),  # noqa: F405
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ──────────────────────────────────────────────
# Background Tasks — production backend
# ──────────────────────────────────────────────
# Using django-tasks DatabaseBackend. Requires a worker process:
#   python manage.py db_worker
INSTALLED_APPS += [  # noqa: F405
    "django_tasks",
    "django_tasks.backends.database",
]
TASKS = {
    "default": {
        "BACKEND": "django_tasks.backends.database.DatabaseBackend",
        "QUEUES": ["default", "notifications", "attachments"],
    }
}

# ──────────────────────────────────────────────
# Email — real SMTP
# ──────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.mailgun.org")  # noqa: F405
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))  # noqa: F405
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")  # noqa: F405
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")  # noqa: F405
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@planly.example.com")  # noqa: F405

# ──────────────────────────────────────────────
# Caching — Redis
# ──────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),  # noqa: F405
    }
}

# ──────────────────────────────────────────────
# Logging — structured JSON for production
# ──────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "django.utils.log.ServerFormatter",
            "format": "%(levelname)s %(asctime)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "level": "WARNING",
        "handlers": ["console"],
    },
    "loggers": {
        "django": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        "planly": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}
```

### `config/settings/test.py` — Optimized for Speed

```python
# config/settings/test.py
from config.settings.base import *  # noqa: F401, F403

DEBUG = False
SECRET_KEY = "insecure-test-key-do-not-use-in-production"  # noqa: F405, S105

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


## Environment Variables

### The `.env.example` File

Every environment variable the project uses should be documented in `.env.example`. This file is committed to version control. The actual `.env` file is gitignored.

```bash
# .env.example — copy to .env and fill in real values

# ──────────────────────────────────────────────
# Django
# ──────────────────────────────────────────────
DJANGO_ENV=development                          # development | production | test
DJANGO_SECRET_KEY=change-me-to-a-random-string  # python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DJANGO_ALLOWED_HOSTS=planly.example.com         # comma-separated, production only

# ──────────────────────────────────────────────
# Database (PostgreSQL)
# ──────────────────────────────────────────────
DB_NAME=planly
DB_USER=planly
DB_PASSWORD=changeme
DB_HOST=localhost
DB_PORT=5432
DB_CONN_MAX_AGE=600

# ──────────────────────────────────────────────
# Redis (production caching)
# ──────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ──────────────────────────────────────────────
# Email (production)
# ──────────────────────────────────────────────
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=noreply@planly.example.com

# ──────────────────────────────────────────────
# Planly
# ──────────────────────────────────────────────
PLANLY_MAX_ATTACHMENT_SIZE_MB=25                # max upload size per file
PLANLY_MAX_BUCKETS_PER_PLAN=200                 # mirrors MS Planner limit
PLANLY_MAX_TASKS_PER_PLAN=9000                  # mirrors MS Planner limit
```

### Why `os.environ` Instead of `django-environ`?

Third-party env libraries add convenience methods like type casting and URL parsing. But for a Postgres-only project like Planly, the standard library covers everything:

- `os.environ["KEY"]` for required values (crashes immediately if missing — that's a feature).
- `os.environ.get("KEY", "default")` for optional values with sensible defaults.
- `int()` for numeric casting.
- `.split(",")` for lists like `ALLOWED_HOSTS`.

One fewer dependency means one fewer thing to audit, version-pin, and keep updated. If your project needs `DATABASE_URL` parsing (e.g., Heroku-style), then `dj-database-url` is a reasonable, focused addition.


## Django 6 TASKS Setting

The `TASKS` setting follows the same pattern as `DATABASES` and `CACHES` — a dictionary of named backends. Planly uses three environments:

| Environment | Backend | Behavior |
|-------------|---------|----------|
| Development | `ImmediateBackend` | Tasks run inline, blocking the request. Simple, no worker process needed. When you assign a task to someone in the board UI, the notification email prints to console immediately. |
| Test | `DummyBackend` | Tasks are captured but never executed. Tests can assert that `send_assignment_notification` was enqueued without actually sending email. |
| Production | `django_tasks.backends.database.DatabaseBackend` | Tasks are stored in PostgreSQL and executed by a separate `db_worker` process. Survives server restarts. Supports queues and priorities. |

Using separate queues in production lets you prioritize work. In Planly, `notifications` should be fast (users expect near-instant assignment emails), while `attachments` (virus scanning, thumbnail generation) can tolerate more latency:

```python
# Enqueue to a specific queue
send_assignment_notification.using(queue_name="notifications").enqueue(
    task_id=task.pk,
    assignee_id=user.pk,
)

# Enqueue attachment processing to the slower queue
process_attachment.using(queue_name="attachments").enqueue(
    attachment_id=attachment.pk,
)
```

### Testing with `DummyBackend`

The `DummyBackend` stores enqueued tasks for inspection. This lets you write tests that verify tasks were enqueued with the right arguments without actually executing them:

```python
# apps/tasks/tests/test_signals.py
from django.test import TestCase, override_settings
from django.tasks import default_task_backend

from plans.tests.factories import BucketFactory
from accounts.tests.factories import UserFactory
from tasks.models import Assignment, Task
from tasks.tests.factories import TaskFactory


class AssignmentSignalTests(TestCase):
    def setUp(self):
        default_task_backend.clear()

    def test_assigning_task_enqueues_notification(self):
        task_obj = TaskFactory()
        assignee = UserFactory()

        Assignment.objects.create(task=task_obj, user=assignee)

        results = default_task_backend.results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].task.name, "tasks.tasks.send_assignment_notification")
```


## Django 6 Content Security Policy

Django 6 ships with native CSP support, replacing the need for `django-csp`. For Planly, CSP is critical because the board UI loads drag-and-drop JavaScript and renders user-generated content (task descriptions, comments).

### Rollout Strategy

Don't enable enforcement immediately — it will break things. Start in report-only mode:

```python
# config/settings/production.py — step 1: report-only
SECURE_CSP_REPORT_ONLY = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF, CSP.NONCE],
    "img-src": [CSP.SELF, "data:", "https:"],
    "report-uri": ["/csp-report/"],
}
```

Monitor the reports. Fix violations (typically inline scripts and styles that need nonces). Then switch to enforcement:

```python
# config/settings/production.py — step 2: enforce
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF, CSP.NONCE],
    "img-src": [CSP.SELF, "data:", "https:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
}
```

### Using Nonces in Templates

Add `django.template.context_processors.csp` to your context processors (already done in `base.py` above). Then use the `csp_nonce` variable in templates:

```html
{# templates/base.html #}
{% load static %}
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="{% static 'css/planly.css' %}" nonce="{{ csp_nonce }}">
</head>
<body>
    {% block content %}{% endblock %}

    <script src="{% static 'js/board.js' %}" nonce="{{ csp_nonce }}"></script>
    <script nonce="{{ csp_nonce }}">
        // Inline script for initializing the drag-and-drop board
        PlanlyBoard.init("{{ plan.pk }}");
    </script>
</body>
</html>
```


## Application-Specific Settings

Planly mirrors several of Microsoft Planner's documented limits. Define these as settings constants (prefixed with `PLANLY_`) so they're easy to find and override per-environment:

```python
# config/settings/base.py
PLANLY_MAX_ATTACHMENT_SIZE_MB = int(os.environ.get("PLANLY_MAX_ATTACHMENT_SIZE_MB", "25"))
PLANLY_MAX_BUCKETS_PER_PLAN = int(os.environ.get("PLANLY_MAX_BUCKETS_PER_PLAN", "200"))
PLANLY_MAX_TASKS_PER_PLAN = int(os.environ.get("PLANLY_MAX_TASKS_PER_PLAN", "9000"))
```

Reference them in validators, views, and forms via `django.conf.settings`:

```python
# apps/plans/models.py
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import OrderedModel, TimeStampedModel


class Bucket(TimeStampedModel, OrderedModel):
    plan = models.ForeignKey("plans.Plan", on_delete=models.CASCADE, related_name="buckets")
    title = models.CharField(max_length=255)

    def clean(self):
        if (
            self.plan_id
            and self.plan.buckets.exclude(pk=self.pk).count()
            >= settings.PLANLY_MAX_BUCKETS_PER_PLAN
        ):
            raise ValidationError(
                f"A plan cannot have more than {settings.PLANLY_MAX_BUCKETS_PER_PLAN} buckets."
            )
```

```python
# apps/attachments/views.py
from django.conf import settings
from django.http import JsonResponse


def upload_attachment(request, task_id):
    file = request.FILES.get("file")
    max_bytes = settings.PLANLY_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024

    if file and file.size > max_bytes:
        return JsonResponse(
            {"error": f"File exceeds {settings.PLANLY_MAX_ATTACHMENT_SIZE_MB}MB limit."},
            status=413,
        )
    # ... proceed with saving
```

**Why prefix with `PLANLY_`?** It prevents collisions with Django's own settings and third-party packages. It also makes it trivial to search the codebase for all application-specific configuration: `grep -r PLANLY_ config/`.


## `manage.py`, `wsgi.py`, and `asgi.py`

All three point to `config.settings` — the `__init__.py` router handles the rest.

```python
# manage.py
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

```python
# config/wsgi.py
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
```

```python
# config/asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_asgi_application()
```


## `pyproject.toml` — Tool Configuration

Keep all tool configuration in one place. Planly's `pyproject.toml` configures ruff, ty, pytest, and coverage:

```toml
[project]
name = "planly"
version = "0.1.0"
requires-python = ">=3.13"

[tool.ruff]
target-version = "py313"
line-length = 99

[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "W",     # pycodestyle warnings
    "F",     # pyflakes
    "I",     # isort
    "B",     # flake8-bugbear
    "C4",    # flake8-comprehensions
    "UP",    # pyupgrade
    "DJ",    # flake8-django
    "S",     # flake8-bandit (security)
]
ignore = [
    "S101",  # allow assert in tests
]

[tool.ruff.lint.isort]
known-first-party = [
    "core", "accounts", "plans", "tasks", "attachments", "notifications",
]

[tool.ty]
python-version = "3.13"

[tool.ty.rules]
possibly-unbound-attribute = "warn"
invalid-assignment = "error"
unresolved-attribute = "error"

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--reuse-db --no-migrations -q"

[tool.coverage.run]
source = ["apps/"]
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 85
show_missing = true
```


## Checklist

1. **Never commit `.env`** — add it to `.gitignore` on day one. Commit `.env.example` with documented defaults.
2. **`SECRET_KEY` via env var** — use `os.environ["DJANGO_SECRET_KEY"]` (hard crash if missing) rather than a default.
3. **Set `AUTH_USER_MODEL` in `base.py`** before the first migration — this cannot be changed later without significant pain.
4. **Start CSP in report-only mode** — add `SECURE_CSP_REPORT_ONLY` first, fix violations, then switch to `SECURE_CSP`.
5. **Use `DummyBackend` for tests** — it lets you assert task enqueuing without executing side effects.
6. **Prefix app settings** with a project-specific namespace (`PLANLY_`) to avoid collisions.
7. **Centralize tool config** in `pyproject.toml` — no more scattered `.flake8`, `setup.cfg`, `ty.toml` files.
-e 

---

# 3. Models & Database



## Philosophy

Models are the foundation of a Django project. Get them right and everything downstream — views, serializers, templates, tests — falls into place naturally. Get them wrong and you'll spend months fighting migrations, writing workaround queries, and patching data integrity bugs that the database should have prevented.

The guiding principle: **push logic and constraints as close to the database as possible.** A `clean()` method can be bypassed; a database constraint cannot. A Python default can be forgotten; a `db_default` cannot.


## Planly's Complete Model Layer

Here is the full model layer for Planly, annotated with every decision explained. We'll break it apart in the sections that follow.

### `core` — Abstract Base Models

```python
# apps/core/models.py
from django.db import models


class TimeStampedModel(models.Model):
    """Every Planly model inherits this for audit timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrderedModel(models.Model):
    """For anything the user can drag-and-drop reorder (buckets, checklist items)."""
    position = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["position"]
```

### `accounts` — Users and Teams

```python
# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import UserManager
from core.models import TimeStampedModel


class User(AbstractUser):
    """Custom user — always define this before the first migration."""
    email = models.EmailField(unique=True)

    # Profile fields — optional, so null=True, blank=True
    display_name = models.CharField(max_length=150, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    job_title = models.CharField(max_length=100, blank=True)

    objects = UserManager()

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.display_name or self.username


class Team(TimeStampedModel):
    """A group of users who collaborate on plans. Maps to a Microsoft 365 Group."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_teams",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    """M2M through model: which users belong to which teams, and in what role."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "user"], name="unique_team_member"),
        ]

    def __str__(self):
        return f"{self.user} — {self.team} ({self.role})"
```

### `plans` — Plans and Buckets

```python
# apps/plans/models.py
from django.conf import settings
from django.db import models

from core.models import OrderedModel, TimeStampedModel


class Plan(TimeStampedModel):
    """A plan is the top-level board — equivalent to a Planner Plan."""

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        PUBLIC = "public", "Public"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    team = models.ForeignKey(
        "accounts.Team",
        on_delete=models.CASCADE,
        related_name="plans",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_plans",
    )
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Bucket(TimeStampedModel, OrderedModel):
    """A column within a plan's board — e.g. 'To Do', 'In Progress', 'Done'."""
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="buckets")
    title = models.CharField(max_length=255)
    color = models.CharField(max_length=7, blank=True)  # hex color like #3498db

    class Meta(OrderedModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "position"],
                name="unique_bucket_position",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]

    def __str__(self):
        return self.title
```

### `tasks` — Tasks, Assignments, Checklists, Labels, Comments

```python
# apps/tasks/models.py
from django.conf import settings
from django.db import models
from django.db.models.functions import Now
from django.utils import timezone

from core.models import OrderedModel, TimeStampedModel


class Label(TimeStampedModel):
    """Colored labels shared across a plan — e.g. 'Urgent', 'Client Review'."""
    plan = models.ForeignKey(
        "plans.Plan",
        on_delete=models.CASCADE,
        related_name="labels",
    )
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#3498db")  # hex

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan", "name"], name="unique_label_per_plan"),
        ]

    def __str__(self):
        return self.name


class Task(TimeStampedModel):
    """The core work item — lives inside a bucket, has assignees, labels, etc."""

    class Priority(models.IntegerChoices):
        URGENT = 1, "Urgent"
        IMPORTANT = 3, "Important"
        MEDIUM = 5, "Medium"
        LOW = 9, "Low"

    class Progress(models.IntegerChoices):
        NOT_STARTED = 0, "Not started"
        IN_PROGRESS = 50, "In progress"
        COMPLETED = 100, "Completed"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    bucket = models.ForeignKey(
        "plans.Bucket",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )

    priority = models.IntegerField(
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    progress = models.IntegerField(
        choices=Progress.choices,
        default=Progress.NOT_STARTED,
    )

    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # M2M relationships
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Assignment",
        related_name="assigned_tasks",
        blank=True,
    )
    labels = models.ManyToManyField(
        Label,
        related_name="tasks",
        blank=True,
    )

    # Recurrence (like Planner's repeat feature)
    recurrence_rule = models.CharField(
        max_length=50,
        blank=True,
        help_text="RRULE fragment: DAILY, WEEKDAYS, WEEKLY, MONTHLY, YEARLY",
    )

    class Meta:
        ordering = ["-priority", "due_date"]
        indexes = [
            models.Index(fields=["bucket", "priority"], name="idx_task_bucket_priority"),
            models.Index(fields=["due_date"], name="idx_task_due_date"),
            models.Index(
                fields=["progress"],
                name="idx_task_incomplete",
                condition=models.Q(progress__lt=100),
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return (
            self.due_date is not None
            and self.due_date < timezone.now().date()
            and self.progress < self.Progress.COMPLETED
        )

    def mark_complete(self):
        self.progress = self.Progress.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["progress", "completed_at", "updated_at"])


class Assignment(TimeStampedModel):
    """Through model for Task ↔ User M2M. Tracks who assigned whom."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assignments_given",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["task", "user"], name="unique_task_assignment"),
        ]

    def __str__(self):
        return f"{self.user} → {self.task}"


class ChecklistItem(TimeStampedModel, OrderedModel):
    """A subtask within a task — a simple checkbox item."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="checklist_items")
    title = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)

    class Meta(OrderedModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["task", "position"],
                name="unique_checklist_position",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]

    def __str__(self):
        return self.title


class Comment(TimeStampedModel):
    """A threaded comment on a task."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="task_comments",
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"
```

### `attachments`

```python
# apps/attachments/models.py
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Attachment(TimeStampedModel):
    """A file attached to a task."""
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_attachments",
    )
    file = models.FileField(upload_to="attachments/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    file_size = models.PositiveIntegerField(help_text="Size in bytes")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.original_filename
```

### `notifications`

```python
# apps/notifications/models.py
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Notification(TimeStampedModel):
    """An in-app notification for a user."""

    class Verb(models.TextChoices):
        ASSIGNED = "assigned", "assigned you to"
        COMMENTED = "commented", "commented on"
        COMPLETED = "completed", "completed"
        DUE_SOON = "due_soon", "is due soon"
        OVERDUE = "overdue", "is overdue"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",  # no reverse relation needed
    )
    verb = models.CharField(max_length=20, choices=Verb.choices)
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "is_read"],
                name="idx_notification_unread",
                condition=models.Q(is_read=False),
            ),
        ]

    def __str__(self):
        return f"{self.actor} {self.verb} {self.task}"
```


## `null` and `blank` — The Complete Guide

This is one of the most misunderstood areas of Django. These two options control different things: `null` is a database concern (does the column allow `NULL`?), and `blank` is a validation concern (can the form field be left empty?). Getting them wrong causes subtle bugs — empty strings mixed with `NULL`, broken filters, inconsistent data.

### The Decision Matrix

| Field type | "Optional" means | Use |
|---|---|---|
| `CharField`, `TextField` | Empty string is fine | `blank=True` only — **never** add `null=True` |
| `DateField`, `DateTimeField` | No value yet | `null=True, blank=True` |
| `IntegerField`, `DecimalField`, `FloatField` | No value yet | `null=True, blank=True` |
| `BooleanField` | Must be True or False | Neither — use `default=` instead |
| `NullBooleanField` / `BooleanField(null=True)` | True, False, or Unknown | `null=True` — only when three-state logic is needed |
| `ForeignKey` | Relationship is optional | `null=True, blank=True` |
| `ForeignKey` (required) | Must always be set | Neither — leave defaults |
| `ManyToManyField` | Zero selections is fine | `blank=True` only — M2M fields **never** use `null` |
| `FileField`, `ImageField` | Upload is optional | `blank=True` only — stores empty string, not `NULL` |
| `EmailField`, `URLField`, `SlugField` | Empty string is fine | `blank=True` only — same rule as `CharField` |
| `JSONField` | No data yet | `null=True, blank=True` or `default=dict` — pick one strategy |

### The Core Rule for String Fields

**Never use `null=True` on `CharField` or `TextField`.** This is the single most important rule.

Why? Because with `null=True`, you get two possible "empty" values: `NULL` and `""`. Now every filter, every template check, every comparison has to account for both:

```python
# BAD — two kinds of "empty" in the database
description = models.TextField(null=True, blank=True)

# Now you need this everywhere:
Task.objects.filter(Q(description__isnull=True) | Q(description=""))

# GOOD — one kind of "empty", always consistent
description = models.TextField(blank=True)

# Clean filtering:
Task.objects.filter(description="")
# Or even better, exclude empty:
Task.objects.exclude(description="")
```

Django's form handling reinforces this: when a `CharField` or `TextField` is submitted empty, Django stores `""` (empty string), not `NULL`. If your column allows `NULL`, you end up with a mix of both from different code paths.

### Planly Examples, Annotated

```python
class Task(TimeStampedModel):
    # ✅ Required string — no null, no blank
    title = models.CharField(max_length=255)

    # ✅ Optional string — blank=True only, never null
    description = models.TextField(blank=True)

    # ✅ Optional date — null=True because dates can't be "empty string"
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    # ✅ Optional datetime — same pattern as dates
    completed_at = models.DateTimeField(null=True, blank=True)

    # ✅ Required FK — bucket must always exist
    bucket = models.ForeignKey("plans.Bucket", on_delete=models.CASCADE, ...)

    # ✅ Optional FK — creator may be deleted
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,            # allows NULL in DB when user is deleted
        related_name="created_tasks",
    )
    # Note: no blank=True on created_by — it's set programmatically, not in a form

    # ✅ Integer with default — not optional, always has a value
    priority = models.IntegerField(choices=Priority.choices, default=Priority.MEDIUM)
    progress = models.IntegerField(choices=Progress.choices, default=Progress.NOT_STARTED)

    # ✅ Boolean — always use a default, never null
    # is_completed = models.BooleanField(default=False)  # not null=True!

    # ✅ M2M — blank=True allows zero selections, never null
    assignees = models.ManyToManyField(..., blank=True)
    labels = models.ManyToManyField(..., blank=True)

    # ✅ Optional string for a non-required feature
    recurrence_rule = models.CharField(max_length=50, blank=True)
```

### `null=True` Without `blank=True` — When the Code Sets the Value

Sometimes a field is nullable in the database but not user-facing. The `created_by` field on a `Plan` uses `null=True` (because `SET_NULL` needs it) but not `blank=True` (because it's set in the view, not a form). The absence of `blank=True` means if someone accidentally puts this field on a form, validation will require it — a safety net.

```python
# Plan.created_by — set in the view, never in a form
created_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,          # DB allows NULL (for when user is deleted)
    # no blank=True     # forms would require it — correct, it should always be set
    related_name="created_plans",
)
```

### `blank=True` Without `null=True` — The String Fields Pattern

This is the most common pattern in Planly. Optional string fields store `""` when empty:

```python
class Bucket(TimeStampedModel, OrderedModel):
    title = models.CharField(max_length=255)        # required
    color = models.CharField(max_length=7, blank=True)  # optional, "" if not set

class User(AbstractUser):
    display_name = models.CharField(max_length=150, blank=True)  # optional
    job_title = models.CharField(max_length=100, blank=True)     # optional
    avatar = models.ImageField(upload_to="avatars/", blank=True) # optional file
```

### `JSONField` — Pick One Strategy and Stick With It

`JSONField` is the one string-ish field where `null=True` is sometimes appropriate. But you must pick one approach and be consistent:

```python
# Strategy A: null=True — "no data" is NULL, "has data" is a dict/list
metadata = models.JSONField(null=True, blank=True)
# Filter: Task.objects.filter(metadata__isnull=False)

# Strategy B: default=dict — always has a value, "no data" is {}
metadata = models.JSONField(default=dict, blank=True)
# Filter: Task.objects.exclude(metadata={})
```

Strategy B (default=dict) is usually cleaner because you never have to handle `NULL` vs `{}`. Planly uses Strategy B for any JSON fields.

### `db_default` — Push Defaults to the Database (Django 5.2+)

Django's `db_default` sets the default at the database level, not just in Python. This matters when rows are inserted outside the ORM (data migrations, raw SQL, other services):

```python
class Notification(TimeStampedModel):
    is_read = models.BooleanField(db_default=False)
    # Even raw SQL inserts will get is_read=FALSE
```

Use `db_default` for values the database can compute. Use Python `default` for values that need Python logic (like `default=timezone.now` for a specific callable).


## Custom Managers and QuerySets

Fat models means putting query logic on custom QuerySets, not in views. This keeps queries reusable, testable, and composable.

```python
# apps/tasks/managers.py
from django.db import models
from django.utils import timezone


class TaskQuerySet(models.QuerySet):
    def for_plan(self, plan):
        """All tasks in a given plan (across all buckets)."""
        return self.filter(bucket__plan=plan)

    def for_user(self, user):
        """Tasks assigned to a specific user."""
        return self.filter(assignments__user=user)

    def overdue(self):
        """Tasks past their due date that aren't completed."""
        return self.filter(
            due_date__lt=timezone.now().date(),
            progress__lt=100,
        )

    def due_today(self):
        """Tasks due today that aren't completed."""
        return self.filter(
            due_date=timezone.now().date(),
            progress__lt=100,
        )

    def by_priority(self):
        """Ordered by priority (urgent first), then due date."""
        return self.order_by("priority", "due_date")

    def with_counts(self):
        """Annotate with checklist completion counts."""
        return self.annotate(
            checklist_total=models.Count("checklist_items"),
            checklist_done=models.Count(
                "checklist_items",
                filter=models.Q(checklist_items__is_completed=True),
            ),
        )

    def incomplete(self):
        return self.filter(progress__lt=100)

    def completed(self):
        return self.filter(progress=100)
```

```python
# apps/plans/managers.py
from django.db import models


class PlanQuerySet(models.QuerySet):
    def for_user(self, user):
        """Plans belonging to teams the user is a member of."""
        return self.filter(team__memberships__user=user)

    def with_task_counts(self):
        """Annotate with total and completed task counts for progress charts."""
        return self.annotate(
            total_tasks=models.Count("buckets__tasks"),
            completed_tasks=models.Count(
                "buckets__tasks",
                filter=models.Q(buckets__tasks__progress=100),
            ),
        )
```

Wire them up in the model:

```python
# apps/tasks/models.py
from tasks.managers import TaskQuerySet

class Task(TimeStampedModel):
    # ... fields ...
    objects = TaskQuerySet.as_manager()
```

Now views stay clean:

```python
# apps/plans/views.py
def plan_board(request, plan_id):
    plan = get_object_or_404(Plan.objects.for_user(request.user), pk=plan_id)
    tasks = Task.objects.for_plan(plan).with_counts().select_related("bucket")
    overdue = Task.objects.for_plan(plan).overdue()
    # ...
```


## Indexes

Indexes speed up reads but slow down writes. Add them deliberately based on how the application actually queries data, not speculatively.

### What Planly Indexes and Why

```python
class Task(TimeStampedModel):
    class Meta:
        indexes = [
            # Board view: fetch all tasks in a bucket, sorted by priority
            models.Index(fields=["bucket", "priority"], name="idx_task_bucket_priority"),

            # "My Tasks" view: find tasks due on a given date
            models.Index(fields=["due_date"], name="idx_task_due_date"),

            # Dashboard: count/fetch incomplete tasks (partial index)
            models.Index(
                fields=["progress"],
                name="idx_task_incomplete",
                condition=models.Q(progress__lt=100),
            ),
        ]
```

```python
class Notification(TimeStampedModel):
    class Meta:
        indexes = [
            # Notification bell: unread count for a user (partial index)
            models.Index(
                fields=["recipient", "is_read"],
                name="idx_notification_unread",
                condition=models.Q(is_read=False),
            ),
        ]
```

### Index Best Practices

**Use `Meta.indexes` instead of `db_index=True`.** The `Meta.indexes` API supports composite indexes, partial indexes (via `condition`), covering indexes, and expression indexes. `db_index=True` only creates single-column B-tree indexes and may be deprecated in the future.

**Name every index explicitly.** Django auto-generates names, but they're cryptic and hit length limits. Use a short, descriptive `name` like `idx_task_due_date`.

**Partial indexes save space and speed.** Planly's `idx_task_incomplete` only indexes tasks where `progress < 100`. Since most tasks eventually complete, this index stays small and fast for the queries that matter (dashboards, overdue checks).

**Composite indexes: leftmost column matters.** `Index(fields=["bucket", "priority"])` supports queries filtering by `bucket` alone or by `bucket` + `priority`, but not by `priority` alone. Order the fields to match your most common query pattern.

**Don't index everything.** If a column is only used in rare admin queries, skip the index. Use `django-debug-toolbar` or `EXPLAIN ANALYZE` to find slow queries in development, then add targeted indexes.


## Constraints

Database constraints enforce data integrity at the lowest level. Unlike `clean()` or `validate_unique()`, constraints cannot be bypassed by raw SQL, bulk operations, or race conditions.

### Planly's Constraints

```python
class Membership(TimeStampedModel):
    class Meta:
        constraints = [
            # A user can only belong to a team once
            models.UniqueConstraint(fields=["team", "user"], name="unique_team_member"),
        ]

class Assignment(TimeStampedModel):
    class Meta:
        constraints = [
            # A user can only be assigned to a task once
            models.UniqueConstraint(fields=["task", "user"], name="unique_task_assignment"),
        ]

class Label(TimeStampedModel):
    class Meta:
        constraints = [
            # No duplicate label names within a plan
            models.UniqueConstraint(fields=["plan", "name"], name="unique_label_per_plan"),
        ]

class Bucket(TimeStampedModel, OrderedModel):
    class Meta:
        constraints = [
            # No two buckets in the same plan can have the same position
            models.UniqueConstraint(
                fields=["plan", "position"],
                name="unique_bucket_position",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]

class ChecklistItem(TimeStampedModel, OrderedModel):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task", "position"],
                name="unique_checklist_position",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]
```

### Deferrable Constraints for Reordering

When the user drags a bucket from position 2 to position 4, you need to shift several rows' positions in one transaction. With an immediate unique constraint, the intermediate state would violate uniqueness. `Deferrable.DEFERRED` tells PostgreSQL to check the constraint at commit time, not on each individual row update:

```python
from django.db import transaction

def reorder_buckets(plan, ordered_bucket_ids):
    """Reorder buckets based on the drag-and-drop result."""
    with transaction.atomic():
        for position, bucket_id in enumerate(ordered_bucket_ids):
            Bucket.objects.filter(pk=bucket_id, plan=plan).update(position=position)
        # Constraint is checked here, at commit — not during each update
```

### CheckConstraints

Use `CheckConstraint` to enforce domain rules the database can validate:

```python
class Task(TimeStampedModel):
    class Meta:
        constraints = [
            # Priority must be a valid choice
            models.CheckConstraint(
                condition=models.Q(priority__in=[1, 3, 5, 9]),
                name="valid_task_priority",
            ),
            # Progress must be 0-100
            models.CheckConstraint(
                condition=models.Q(progress__gte=0, progress__lte=100),
                name="valid_task_progress",
            ),
            # If completed_at is set, progress must be 100
            models.CheckConstraint(
                condition=(
                    models.Q(completed_at__isnull=True)
                    | models.Q(progress=100)
                ),
                name="completed_implies_full_progress",
            ),
            # start_date must be before or equal to due_date
            models.CheckConstraint(
                condition=(
                    models.Q(start_date__isnull=True)
                    | models.Q(due_date__isnull=True)
                    | models.Q(start_date__lte=models.F("due_date"))
                ),
                name="start_before_due",
            ),
        ]
```


## `on_delete` — Choosing the Right Strategy

Every `ForeignKey` and `OneToOneField` requires an `on_delete` argument. Here's what Planly uses and why:

| `on_delete` | Planly usage | When to use |
|---|---|---|
| `CASCADE` | `Bucket.plan`, `Task.bucket`, `Comment.task`, `ChecklistItem.task` | When the child has no meaning without the parent. Deleting a plan should delete its buckets; deleting a bucket should delete its tasks. |
| `SET_NULL` | `Task.created_by`, `Comment.author`, `Attachment.uploaded_by` | When the parent is optional and the child should survive. If a user is deleted, their tasks and comments remain but `created_by` becomes `NULL`. Requires `null=True`. |
| `PROTECT` | `Team.owner` | When deleting the parent would be destructive and should be explicitly prevented. You must reassign ownership before deleting a team owner. |
| `SET_DEFAULT` | (Not used in Planly) | Rarely useful. Sets the FK to a default value when the parent is deleted. |
| `DO_NOTHING` | (Not used in Planly) | Dangerous. Leaves orphaned FKs. Only use if you're managing referential integrity yourself (e.g., triggers). |

A common mistake is using `CASCADE` everywhere. Ask yourself: "if I delete this parent row, should all these children silently disappear?" If the answer is "no" or "it depends", use `SET_NULL` or `PROTECT`.


## `choices` — Use IntegerChoices and TextChoices

Django's enum-based choices (introduced in 3.0) are the standard. They provide type safety, readable code, and work well with both forms and the admin.

```python
class Priority(models.IntegerChoices):
    URGENT = 1, "Urgent"
    IMPORTANT = 3, "Important"
    MEDIUM = 5, "Medium"
    LOW = 9, "Low"

# In queries — readable and refactor-safe
Task.objects.filter(priority=Task.Priority.URGENT)

# In templates
{{ task.get_priority_display }}

# Comparison
if task.priority <= Task.Priority.IMPORTANT:
    send_urgent_notification(task)
```

**Use `IntegerChoices` when the values have semantic ordering** (priority, progress). Use `TextChoices` when the values are categorical labels (role, visibility, notification verb).

**Leave gaps between integer values** (1, 3, 5, 9 instead of 1, 2, 3, 4). This lets you insert new priority levels later without renumbering existing data.


## `related_name` — Always Set It Explicitly

Django auto-generates reverse relation names, but they're often awkward or ambiguous. When a model has multiple FKs to the same target (like `Task` having both `created_by` and `assignees` pointing to `User`), auto-generated names collide.

```python
# BAD — collision: User already has a "task_set" from created_by
assignees = models.ManyToManyField(User, ...)
created_by = models.ForeignKey(User, ...)

# GOOD — explicit, descriptive reverse names
assignees = models.ManyToManyField(User, related_name="assigned_tasks", ...)
created_by = models.ForeignKey(User, related_name="created_tasks", ...)
```

Use `related_name="+"` when you don't need the reverse relation at all:

```python
class Notification(TimeStampedModel):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    # We never need user.notification_set for actors — only for recipients
```


## `__str__` and Model Methods

Every model should define `__str__`. It shows up in the admin, in error messages, in shell debugging, and in log output. Keep it short and unambiguous:

```python
class Task(TimeStampedModel):
    def __str__(self):
        return self.title          # "Fix login page" — clear and concise

class Assignment(TimeStampedModel):
    def __str__(self):
        return f"{self.user} → {self.task}"  # "alice → Fix login page"

class Comment(TimeStampedModel):
    def __str__(self):
        return f"Comment by {self.author} on {self.task}"
```

Put domain logic on the model as methods or properties. This is the "fat models" principle — views and templates should call methods, not compute things themselves:

```python
class Task(TimeStampedModel):
    @property
    def is_overdue(self):
        """Used in templates: {% if task.is_overdue %} and in querysets."""
        return (
            self.due_date is not None
            and self.due_date < timezone.now().date()
            and self.progress < self.Progress.COMPLETED
        )

    def mark_complete(self):
        """Encapsulates the side effects of completing a task."""
        self.progress = self.Progress.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["progress", "completed_at", "updated_at"])
```


## Migration Hygiene

Migrations are version-controlled database changes. Treat them with the same care as application code.

**Never mix schema changes and data changes in the same migration.** Schema migrations acquire locks; data migrations can be slow. Combining them extends the lock duration and can cause downtime. Use `RunPython` in a separate migration for data backfills.

**Name migrations descriptively.** Django's auto-generated names (`0003_auto_20260318_1422`) tell you nothing. Rename them after creation:

```bash
# After running makemigrations:
mv apps/tasks/migrations/0003_auto_20260318_1422.py \
   apps/tasks/migrations/0003_add_recurrence_rule_to_task.py
```

**Always commit migrations.** If two developers both run `makemigrations` against the same model change, you get conflicting migrations. Commit early and rebase often.

**Squash when they pile up.** After a model stabilizes, squash the migration chain to reduce startup time and simplify the history:

```bash
python manage.py squashmigrations tasks 0001 0010
```

**Test migrations on a copy of production data.** A migration that works on an empty test database can fail on a table with millions of rows. Run `migrate` against a staging database with realistic data before deploying.


## Composite Primary Keys (Django 5.2+)

Django now supports composite primary keys via `CompositePrimaryKey`. In Planly, `Assignment` (the through model linking tasks to users) is a natural candidate — it's uniquely identified by `(task, user)`:

```python
# Alternative design using CompositePrimaryKey
class Assignment(TimeStampedModel):
    pk = models.CompositePrimaryKey("task", "user")
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assignments_given",
    )
```

**When to use composite PKs:** Junction/through tables where the combination of two FKs is the natural key. Saves an unnecessary `id` column and index.

**When to avoid them:** Composite PKs don't yet work with the Django admin, and some third-party packages assume a single integer PK. For Planly, we use the standard auto-generated `BigAutoField` PK with a `UniqueConstraint` instead — it's simpler and fully compatible with the admin and all third-party packages. Consider composite PKs when compatibility isn't a concern.


## Checklist

1. **Define `AUTH_USER_MODEL` and create `accounts.User`** before the first migration — always, even if it's identical to `AbstractUser` at first.
2. **Never use `null=True` on `CharField` or `TextField`** — use `blank=True` alone for optional strings.
3. **Use `null=True, blank=True` together** for optional dates, datetimes, numbers, and FKs.
4. **Use `default=` for booleans and integer choices** — avoid nullable booleans unless you need three-state logic.
5. **Choose `on_delete` deliberately** — `CASCADE` for dependent children, `SET_NULL` for preserving orphans, `PROTECT` for preventing accidental data loss.
6. **Set `related_name` on every FK and M2M** — especially when a model has multiple relations to the same target.
7. **Use `Meta.indexes` with explicit names** — prefer partial and composite indexes over blanket `db_index=True`.
8. **Use `UniqueConstraint` over `unique_together`** — the older syntax is effectively deprecated.
9. **Use `Deferrable.DEFERRED`** on position uniqueness constraints to support drag-and-drop reordering.
10. **Put domain logic on models**, not in views — properties like `is_overdue` and methods like `mark_complete()`.
11. **Never mix schema and data migrations** — separate them for safety and speed.
12. **Keep `core` abstract-only** — no tables, no views, no URLs.
-e 

---

# 4. Views & URL Routing



## When to Use CBVs vs FBVs

Use **function-based views (FBVs)** for simple, one-off endpoints — a JSON reorder endpoint, a notification mark-as-read toggle, an HTMX partial response. Use **class-based views (CBVs)** when you're doing standard CRUD that maps cleanly to Django's generic views (`ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView`).

The mistake teams make is forcing everything into one style. Planly uses both:

```python
# apps/plans/views.py — CBVs for standard CRUD
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, ListView

from plans.models import Plan


class PlanListView(LoginRequiredMixin, ListView):
    model = Plan
    template_name = "plans/plan_list.html"
    context_object_name = "plans"

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user).with_task_counts()


class PlanCreateView(LoginRequiredMixin, CreateView):
    model = Plan
    fields = ["title", "description", "team", "visibility"]
    template_name = "plans/plan_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
```

```python
# apps/tasks/views.py — FBV for a drag-and-drop reorder endpoint
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from plans.models import Bucket
from tasks.views_helpers import reorder_buckets


@require_POST
def bucket_reorder(request, plan_id):
    """HTMX/JS calls this when the user drags a bucket to a new position."""
    ordered_ids = json.loads(request.body).get("bucket_ids", [])
    plan = Plan.objects.for_user(request.user).get(pk=plan_id)
    reorder_buckets(plan, ordered_ids)
    return JsonResponse({"status": "ok"})
```

## Keep Business Logic Out of Views

Views should orchestrate — receive a request, call domain logic, return a response. If a view function is longer than ~20 lines, logic is leaking in.

```python
# BAD — business logic in the view
@require_POST
def complete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    task.progress = 100
    task.completed_at = timezone.now()
    task.save()
    Notification.objects.create(
        recipient=task.created_by, actor=request.user,
        verb="completed", task=task,
    )
    return redirect("plans:plan-board", plan_id=task.bucket.plan_id)

# GOOD — view calls model method, signal handles notification
@require_POST
def complete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    task.mark_complete()  # model method from Section 3
    return redirect("plans:plan-board", plan_id=task.bucket.plan_id)
```

## URL Routing

### Namespacing

Every app gets its own `urls.py` with an `app_name` for namespacing:

```python
# apps/plans/urls.py
from django.urls import path

from plans import views

app_name = "plans"

urlpatterns = [
    path("", views.PlanListView.as_view(), name="plan-list"),
    path("create/", views.PlanCreateView.as_view(), name="plan-create"),
    path("<int:plan_id>/board/", views.plan_board, name="plan-board"),
    path("<int:plan_id>/buckets/reorder/", views.bucket_reorder, name="bucket-reorder"),
]
```

```python
# apps/tasks/urls.py
from django.urls import path

from tasks import views

app_name = "tasks"

urlpatterns = [
    path("<int:task_id>/", views.task_detail, name="task-detail"),
    path("<int:task_id>/complete/", views.complete_task, name="task-complete"),
    path("<int:task_id>/comment/", views.add_comment, name="task-comment"),
    path("<int:task_id>/checklist/", views.add_checklist_item, name="checklist-add"),
    path(
        "checklist/<int:item_id>/toggle/",
        views.toggle_checklist_item,
        name="checklist-toggle",
    ),
]
```

### Reverse URLs in Templates and Code

Always use `{% url %}` and `reverse()` — never hardcode paths:

```html
{# templates/plans/plan_list.html #}
<a href="{% url 'plans:plan-create' %}">New Plan</a>
<a href="{% url 'plans:plan-board' plan_id=plan.pk %}">{{ plan.title }}</a>
```

```python
from django.urls import reverse
return redirect(reverse("plans:plan-board", kwargs={"plan_id": plan.pk}))
```


---

# 5. Forms & Validation

## Forms for Server-Rendered Views

Planly is server-rendered with HTMX enhancements. Forms are the standard way to handle user input.

### Centralize Validation Logic

Put validation in the form or the model — not the view. Forms handle field-level cleaning; models handle cross-field and database-level constraints.

```python
# apps/tasks/forms.py
from django import forms
from django.conf import settings

from tasks.models import ChecklistItem, Comment, Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title", "description", "bucket", "priority",
            "start_date", "due_date", "assignees", "labels",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        due = cleaned.get("due_date")
        if start and due and start > due:
            raise forms.ValidationError("Start date must be before or equal to due date.")
        return cleaned

    def clean_title(self):
        title = self.cleaned_data["title"]
        if len(title.strip()) < 2:
            raise forms.ValidationError("Title must be at least 2 characters.")
        return title.strip()


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 2, "placeholder": "Write a comment..."}),
        }


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ["title"]
```

### Using Forms in Views

```python
# apps/tasks/views.py
from django.shortcuts import get_object_or_404, redirect, render

from tasks.forms import CommentForm
from tasks.models import Task


def task_detail(request, task_id):
    task = get_object_or_404(
        Task.objects.select_related("bucket__plan").prefetch_related(
            "assignees", "labels", "checklist_items", "comments__author",
        ),
        pk=task_id,
    )
    comment_form = CommentForm()

    if request.method == "POST":
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            return redirect("tasks:task-detail", task_id=task.pk)

    return render(request, "tasks/task_detail.html", {
        "task": task,
        "comment_form": comment_form,
    })
```


---

# 6. Templates & Frontend

## Template Inheritance

Use a three-level hierarchy — base, section, page:

```html
{# templates/base.html — site-wide skeleton #}
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}Planly{% endblock %}</title>
    <link rel="stylesheet" href="{% static 'css/planly.css' %}" nonce="{{ csp_nonce }}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    {% include "partials/_navbar.html" %}
    <main>
        {% block content %}{% endblock %}
    </main>
    <script src="{% static 'js/htmx.min.js' %}" nonce="{{ csp_nonce }}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

```html
{# templates/plans/plan_board.html — page template #}
{% extends "base.html" %}

{% block title %}{{ plan.title }} — Planly{% endblock %}

{% block content %}
<div class="board">
    {% for bucket in plan.buckets.all %}
        {% include "plans/partials/_bucket_column.html" with bucket=bucket %}
    {% endfor %}
</div>
{% endblock %}
```

## Django 6 Template Partials

Django 6 introduces `{% partialdef %}` and `{% partial %}`, eliminating the need to split every reusable fragment into a separate file. This is especially useful for HTMX, where you frequently return small HTML snippets.

```html
{# templates/tasks/task_card.html #}

{# Define a partial that can be rendered standalone or included #}
{% partialdef task_card %}
<div class="task-card" id="task-{{ task.pk }}">
    <h4>{{ task.title }}</h4>
    {% if task.is_overdue %}<span class="badge overdue">Overdue</span>{% endif %}
    <div class="meta">
        {{ task.get_priority_display }} · {{ task.assignees.count }} assigned
    </div>
    {% if task.checklist_items.exists %}
    <div class="checklist-progress">
        {{ task.checklist_done }}/{{ task.checklist_total }}
    </div>
    {% endif %}
</div>
{% endpartialdef %}
```

Return just the partial from an HTMX view:

```python
# apps/tasks/views.py
def toggle_checklist_item(request, item_id):
    item = get_object_or_404(ChecklistItem, pk=item_id)
    item.is_completed = not item.is_completed
    item.save(update_fields=["is_completed", "updated_at"])
    task = item.task
    return render(request, "tasks/task_card.html#task_card", {"task": task})
```

## Keep Logic Out of Templates

Templates should display data, not compute it. If you're writing `{% if %}` chains that span 10+ lines, that logic belongs in the model, a template tag, or the view context.

```html
{# BAD — computing in the template #}
{% if task.due_date and task.due_date < today and task.progress < 100 %}
    <span class="overdue">Overdue</span>
{% endif %}

{# GOOD — property on the model #}
{% if task.is_overdue %}
    <span class="overdue">Overdue</span>
{% endif %}
```


---

# 7. Testing

## Test Stack

Planly uses **pytest-django** with **factory_boy**. Configure in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
addopts = "--reuse-db --no-migrations -q"
```

`--reuse-db` skips database teardown/recreation between runs. `--no-migrations` uses `syncdb` instead — dramatically faster for test suites.

## Factory Boy Over Fixtures

Fixtures are brittle and hard to maintain. Factories are composable, readable, and create exactly the data each test needs:

```python
# apps/tasks/tests/factories.py
import factory
from factory.django import DjangoModelFactory

from accounts.tests.factories import UserFactory
from plans.tests.factories import BucketFactory
from tasks.models import Task


class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    title = factory.Sequence(lambda n: f"Task {n}")
    bucket = factory.SubFactory(BucketFactory)
    created_by = factory.SubFactory(UserFactory)
    priority = Task.Priority.MEDIUM
    progress = Task.Progress.NOT_STARTED
```

```python
# apps/plans/tests/factories.py
import factory
from factory.django import DjangoModelFactory

from accounts.tests.factories import TeamFactory
from plans.models import Bucket, Plan


class PlanFactory(DjangoModelFactory):
    class Meta:
        model = Plan

    title = factory.Sequence(lambda n: f"Plan {n}")
    team = factory.SubFactory(TeamFactory)


class BucketFactory(DjangoModelFactory):
    class Meta:
        model = Bucket

    plan = factory.SubFactory(PlanFactory)
    title = factory.Sequence(lambda n: f"Bucket {n}")
    position = factory.Sequence(lambda n: n)
```

## What to Test at Each Layer

**Models** — test custom methods, properties, constraints, manager querysets:

```python
# apps/tasks/tests/test_models.py
import pytest
from django.utils import timezone
from datetime import timedelta

from tasks.tests.factories import TaskFactory


@pytest.mark.django_db
class TestTaskModel:
    def test_is_overdue_true_when_past_due(self):
        task = TaskFactory(
            due_date=timezone.now().date() - timedelta(days=1),
            progress=Task.Progress.NOT_STARTED,
        )
        assert task.is_overdue is True

    def test_is_overdue_false_when_completed(self):
        task = TaskFactory(
            due_date=timezone.now().date() - timedelta(days=1),
            progress=Task.Progress.COMPLETED,
        )
        assert task.is_overdue is False

    def test_mark_complete_sets_progress_and_timestamp(self):
        task = TaskFactory()
        task.mark_complete()
        task.refresh_from_db()
        assert task.progress == Task.Progress.COMPLETED
        assert task.completed_at is not None
```

**Views** — test HTTP status, redirects, context, and permissions:

```python
# apps/plans/tests/test_views.py
import pytest
from django.test import Client

from accounts.tests.factories import MembershipFactory, UserFactory
from plans.tests.factories import PlanFactory


@pytest.mark.django_db
class TestPlanBoard:
    def test_member_can_view_board(self):
        membership = MembershipFactory()
        plan = PlanFactory(team=membership.team)
        client = Client()
        client.force_login(membership.user)

        response = client.get(f"/plans/{plan.pk}/board/")

        assert response.status_code == 200
        assert plan.title in response.content.decode()

    def test_non_member_gets_404(self):
        plan = PlanFactory()
        outsider = UserFactory()
        client = Client()
        client.force_login(outsider)

        response = client.get(f"/plans/{plan.pk}/board/")

        assert response.status_code == 404
```

**Background tasks** — test enqueuing with `DummyBackend`:

```python
# apps/tasks/tests/test_tasks.py
import pytest
from django.tasks import default_task_backend

from accounts.tests.factories import UserFactory
from tasks.models import Assignment
from tasks.tests.factories import TaskFactory


@pytest.mark.django_db
class TestAssignmentNotification:
    def setup_method(self):
        default_task_backend.clear()

    def test_assignment_enqueues_notification_task(self):
        task = TaskFactory()
        user = UserFactory()
        Assignment.objects.create(task=task, user=user, assigned_by=task.created_by)

        results = default_task_backend.results
        assert len(results) == 1
        assert "send_assignment_notification" in results[0].task.name
```

## Coverage Expectations

Set a minimum in `pyproject.toml` and enforce it in CI:

```toml
[tool.coverage.run]
source = ["apps/"]
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 85
show_missing = true
```

85% is a practical floor. 100% is a vanity metric — don't chase it. Focus coverage on models, business logic, and permission checks. Admin configuration and boilerplate `apps.py` files don't need tests.


---

# 8. Security Hardening

## CSP (Covered in Section 2)

Django 6's native `ContentSecurityPolicyMiddleware` with `SECURE_CSP` is configured in `production.py`. Refer to Section 2 for the full rollout strategy.

## CSRF

Django's CSRF protection is on by default. Don't disable it. For HTMX, include the token in a meta tag and configure HTMX to send it:

```html
{# templates/base.html #}
<meta name="csrf-token" content="{{ csrf_token }}">
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

## CORS

If Planly serves a REST API consumed by a separate frontend, CORS must be configured. See Section 13 (REST APIs) for full `django-cors-headers` setup.

## Rate Limiting

Protect login and API endpoints from brute-force with `django-ratelimit`:

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def login_view(request):
    # ...
```

## Permission Checks

Never rely on URL obscurity for access control. Every view that mutates data should verify the user has permission:

```python
# apps/tasks/views.py
def complete_task(request, task_id):
    task = get_object_or_404(
        Task.objects.filter(bucket__plan__team__memberships__user=request.user),
        pk=task_id,
    )
    task.mark_complete()
    return redirect("plans:plan-board", plan_id=task.bucket.plan_id)
```

The queryset filter ensures the user is a member of the team that owns the plan. If they aren't, `get_object_or_404` returns 404 — not a 403 that leaks the object's existence.

## Production Security Settings

These are in `production.py` (Section 2) but worth repeating:

```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```


---

# 9. Performance & Query Optimization

## N+1 Detection and Prevention

The board view is Planly's most query-intensive page — it loads a plan with all its buckets, each bucket's tasks, each task's assignees and labels. Without optimization, this is a classic N+1 disaster.

### `select_related` — Follow FK/OneToOne in a JOIN

```python
# Single JOIN: fetch task + bucket + plan in one query
task = Task.objects.select_related("bucket__plan").get(pk=task_id)
# task.bucket.plan.title — no additional queries
```

### `prefetch_related` — Separate Query for M2M/Reverse FK

```python
# Board view: 4 queries total instead of hundreds
plan = Plan.objects.prefetch_related(
    "buckets__tasks__assignees",
    "buckets__tasks__labels",
    "buckets__tasks__checklist_items",
).get(pk=plan_id)
```

### Use `django-debug-toolbar` in Development

Add it to `development.py` (already done in Section 2). The SQL panel shows every query, its duration, and whether it's duplicated. Run through every page in the app and fix anything with more than ~10 queries.

### `Prefetch` Objects for Filtered Prefetches

The "My Tasks" view only needs incomplete tasks assigned to the current user:

```python
from django.db.models import Prefetch

plans = Plan.objects.for_user(request.user).prefetch_related(
    Prefetch(
        "buckets__tasks",
        queryset=Task.objects.filter(
            assignments__user=request.user,
            progress__lt=100,
        ).select_related("bucket"),
    ),
)
```

## `update_fields` on `save()`

When you only change one or two fields, tell Django so it generates a leaner `UPDATE`:

```python
# Updates only 3 columns instead of all ~15
task.progress = Task.Progress.COMPLETED
task.completed_at = timezone.now()
task.save(update_fields=["progress", "completed_at", "updated_at"])
```

## Caching Strategy

Planly's caching priorities:

```python
# config/settings/production.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    }
}
```

**Cache expensive aggregations**, not individual model instances:

```python
from django.core.cache import cache

def get_plan_stats(plan_id):
    cache_key = f"plan_stats:{plan_id}"
    stats = cache.get(cache_key)
    if stats is None:
        stats = Plan.objects.filter(pk=plan_id).with_task_counts().values(
            "total_tasks", "completed_tasks"
        ).first()
        cache.set(cache_key, stats, timeout=300)  # 5 minutes
    return stats
```

Invalidate on task completion:

```python
# apps/tasks/signals.py
@receiver(post_save, sender=Task)
def invalidate_plan_stats_cache(sender, instance, **kwargs):
    cache.delete(f"plan_stats:{instance.bucket.plan_id}")
```

## Pagination

Never load unbounded querysets. Planly's plan list and notification list are paginated:

```python
from django.core.paginator import Paginator

def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    paginator = Paginator(notifications, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "notifications/list.html", {"page": page})
```

For async views, Django 6 provides `AsyncPaginator` and `AsyncPage`.


---

# 10. Code Quality & Tooling

## The Astral Toolchain: Ruff + ty

Planly standardizes on the Astral toolchain — **Ruff** for linting and formatting, **ty** for type checking. Both are written in Rust, both are orders of magnitude faster than their predecessors, and they share configuration style.

### Ruff — Linter and Formatter

Ruff replaces flake8, isort, black, pyupgrade, and bandit in a single tool. Configure in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py313"
line-length = 99

[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "W",     # pycodestyle warnings
    "F",     # pyflakes
    "I",     # isort
    "B",     # flake8-bugbear
    "C4",    # flake8-comprehensions
    "UP",    # pyupgrade
    "DJ",    # flake8-django
    "S",     # flake8-bandit (security)
]
ignore = [
    "S101",  # allow assert in tests
]

[tool.ruff.lint.isort]
known-first-party = [
    "core", "accounts", "plans", "tasks", "attachments", "notifications",
]

[tool.ruff.format]
quote-style = "double"
```

Run:

```bash
ruff check .          # lint
ruff check . --fix    # lint + autofix
ruff format .         # format (replaces black)
```

### ty — Type Checker

ty is Astral's type checker — 10–60x faster than mypy, with richer diagnostics and a built-in language server for editor integration. Install with `uv tool install ty@latest`.

Configure in `pyproject.toml`:

```toml
[tool.ty]
python-version = "3.13"

[tool.ty.rules]
possibly-unbound-attribute = "warn"     # catch missing attrs
invalid-assignment = "error"            # type mismatch on assignment
unresolved-attribute = "error"          # typos in attribute access
```

Run:

```bash
ty check                    # check entire project
ty check apps/tasks/        # check one app
```

ty works well with Django even without full stub support — it catches attribute typos, wrong argument types, and unreachable code. As Django stubs mature for ty, coverage will improve further. For now, use it alongside your test suite as a fast first-pass check.

### Editor Integration

ty includes a language server. Install the VS Code extension (`astral-sh.ty`) for go-to-definition, auto-complete, inline diagnostics, and rename refactoring — all powered by the same type analysis engine.

## Pre-commit Hooks

Enforce code quality before code reaches the repository:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

Install:

```bash
pip install pre-commit
pre-commit install
```

## Type Hints in Planly

Add type hints progressively. Start with model methods and utility functions — the highest-value targets:

```python
# apps/tasks/models.py
from datetime import date

class Task(TimeStampedModel):
    @property
    def is_overdue(self) -> bool:
        return (
            self.due_date is not None
            and self.due_date < timezone.now().date()
            and self.progress < self.Progress.COMPLETED
        )

    def mark_complete(self) -> None:
        self.progress = self.Progress.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["progress", "completed_at", "updated_at"])
```

```python
# apps/tasks/managers.py
from django.db import models

class TaskQuerySet(models.QuerySet):
    def overdue(self) -> "TaskQuerySet":
        return self.filter(
            due_date__lt=timezone.now().date(),
            progress__lt=100,
        )
```

Don't annotate every line of every view on day one. Focus on the boundaries: public functions, model methods, and anything called from multiple places.


---

# 11. Deployment & DevOps

## Gunicorn Configuration

Planly runs behind Gunicorn in production. Create a `gunicorn.conf.py` at the repo root:

```python
# gunicorn.conf.py
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 4
timeout = 30
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Graceful restarts
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 50
```

`max_requests` recycles workers after 1000 requests to prevent memory leaks. `max_requests_jitter` staggers the restarts so all workers don't restart at once.

For async views, use `uvicorn.workers.UvicornWorker`:

```python
worker_class = "uvicorn.workers.UvicornWorker"
```

## Static Files with WhiteNoise

Run `collectstatic` in CI, not on deploy:

```bash
# In your CI/CD pipeline or Dockerfile
python manage.py collectstatic --noinput
```

WhiteNoise serves them directly from the WSGI app — no nginx needed for static files. Configured in `production.py` (Section 2).

## Health Check Endpoint

Add a simple endpoint that verifies the database connection. Load balancers and orchestrators use this to determine instance health:

```python
# config/urls.py
from django.http import JsonResponse
from django.db import connection


def health_check(request):
    try:
        connection.ensure_connection()
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "error"}, status=503)


urlpatterns = [
    path("health/", health_check, name="health-check"),
    # ... other urls
]
```

## Structured Logging

Production logs should be machine-parseable. Use `structlog` for structured JSON output:

```bash
pip install structlog
```

```python
# config/settings/production.py
import structlog

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer()
            if DEBUG
            else structlog.processors.JSONRenderer(),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "level": "WARNING",
        "handlers": ["console"],
    },
    "loggers": {
        "planly": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}
```

Use it in application code:

```python
import structlog

logger = structlog.get_logger("planly.tasks")

def send_assignment_notification(task_id: int, assignee_id: int) -> None:
    logger.info("sending_assignment_notification", task_id=task_id, assignee_id=assignee_id)
    # ...
```

## Running Background Workers

In production, the `django-tasks` DatabaseBackend needs a worker process:

```bash
python manage.py db_worker
```

Run this as a separate container or process alongside the web server. In Docker Compose, it's a separate service (see Section 12).


---

# 12. Docker & Docker Compose

## Dockerfile — Multi-Stage Build

```dockerfile
# Dockerfile
# ─── Stage 1: Build ──────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

# Install system dependencies for psycopg (PostgreSQL)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements/production.txt requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Runtime ────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Runtime-only system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    addgroup --system planly && \
    adduser --system --ingroup planly planly

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Collect static files at build time
RUN python manage.py collectstatic --noinput

# Switch to non-root user
USER planly

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]
```

Key decisions: multi-stage keeps the image small by not including gcc and build headers in the final image. Static files are collected at build time, not runtime. The app runs as a non-root user.

## Docker Compose — Local Development

```yaml
# docker-compose.yml
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

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DJANGO_ENV: development
      DB_HOST: db
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build: .
    command: python manage.py db_worker
    volumes:
      - .:/app
    env_file: .env
    environment:
      DJANGO_ENV: development
      DB_HOST: db
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

### Service Breakdown

| Service | Purpose | Notes |
|---------|---------|-------|
| `db` | PostgreSQL 17 | Named volume for data persistence across restarts. Health check with `pg_isready`. |
| `redis` | Cache and (optionally) task broker | Alpine image keeps it small. Used by `django.core.cache.backends.redis.RedisCache`. |
| `web` | Django dev server | Bind-mounts the repo for live reload. Overrides `CMD` to use `runserver` instead of Gunicorn. |
| `worker` | Background task worker | Runs `db_worker` for the Django 6 tasks framework. Same codebase, different entrypoint. |

### Entrypoint Script (Optional)

For production-like local testing, use an entrypoint that waits for the database and runs migrations:

```bash
#!/bin/bash
# scripts/entrypoint.sh
set -e

echo "Waiting for database..."
while ! python -c "import psycopg; psycopg.connect('${DATABASE_URL}')" 2>/dev/null; do
    sleep 1
done

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting server..."
exec "$@"
```

```yaml
# docker-compose.override.yml — dev-only entrypoint
services:
  web:
    entrypoint: ["bash", "scripts/entrypoint.sh"]
```

## Production Docker Compose

For production-like local testing, use a separate override:

```yaml
# docker-compose.prod.yml
services:
  web:
    command: gunicorn config.wsgi:application -c gunicorn.conf.py
    volumes: []  # no bind mount — use built image
    environment:
      DJANGO_ENV: production
```

Run with:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up
```

## `.dockerignore`

Keep images lean:

```
# .dockerignore
.git
.env
*.pyc
__pycache__
media/
staticfiles/
.venv/
node_modules/
docs/
*.md
.pre-commit-config.yaml
docker-compose*.yml
```


---

# 13. REST APIs with Django REST Framework

## When to Add an API Layer

Planly starts as a server-rendered Django application with HTMX. But mobile apps, third-party integrations, and single-page frontend rewrites all need a structured API. Django REST Framework (DRF) is the standard toolkit for this — it provides serialization, authentication, permissions, pagination, throttling, and a browsable API out of the box.

This section covers how Planly layers a DRF API alongside its existing server-rendered views without disrupting the codebase.


## Project Structure for APIs

Keep API code in a dedicated `api/` subpackage within each app. This cleanly separates API serializers, views, and URLs from server-rendered forms, views, and templates:

```
apps/tasks/
├── api/
│   ├── __init__.py
│   ├── serializers.py     ← DRF serializers
│   ├── views.py           ← ViewSets and APIViews
│   ├── urls.py            ← router and API URL patterns
│   ├── permissions.py     ← custom permission classes
│   └── filters.py         ← django-filter FilterSets
├── forms.py               ← server-rendered forms (Section 5)
├── models.py
├── views.py               ← server-rendered views (Section 4)
└── ...

apps/plans/
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── permissions.py
├── models.py
├── views.py
└── ...
```

This structure means adding an API doesn't touch existing server-rendered code. Both can coexist indefinitely.


## Settings for DRF

Add DRF and related packages to `INSTALLED_APPS` and configure defaults in `base.py`:

```python
# config/settings/base.py
INSTALLED_APPS = [
    # ... existing apps ...
    "rest_framework",
    "django_filters",
    "drf_spectacular",
]

REST_FRAMEWORK = {
    # Authentication
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Permissions
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Pagination
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    # Filtering
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Throttling
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
    },
    # Schema
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Rendering
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",  # remove in production if desired
    ],
    # Dates
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%SZ",
    "DATE_FORMAT": "%Y-%m-%d",
}
```

### JWT Configuration

```python
# config/settings/base.py
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
```

### API Documentation Settings

```python
# config/settings/base.py
SPECTACULAR_SETTINGS = {
    "TITLE": "Planly API",
    "DESCRIPTION": "Task management API — a Microsoft Planner-style application.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,  # separate request/response schemas
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]",
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
    },
}
```


## Serializers

Serializers are the bridge between Django models and JSON. They handle validation on the way in and representation on the way out.

### Principles

**Use `ModelSerializer` for standard CRUD.** It generates fields from the model, handles create/update, and respects model-level validation.

**Use separate serializers for list vs detail.** List views should be lightweight (fewer fields, no nested relations). Detail views can include nested data.

**Never use `fields = "__all__"`.** It exposes every field, including ones you didn't intend (timestamps, internal flags). Always list fields explicitly.

**Mark non-input fields as `read_only`.** This skips validation on those fields and makes the schema clearer for API consumers.

### Planly Serializers

```python
# apps/tasks/api/serializers.py
from rest_framework import serializers

from accounts.api.serializers import UserSummarySerializer
from tasks.models import Assignment, ChecklistItem, Comment, Label, Task


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ["id", "name", "color"]


class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ["id", "title", "is_completed", "position"]
        read_only_fields = ["id"]


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "body", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class TaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for board/list views."""
    assignee_count = serializers.IntegerField(source="assignments.count", read_only=True)
    checklist_progress = serializers.SerializerMethodField()
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id", "title", "priority", "progress",
            "due_date", "assignee_count", "checklist_progress",
            "is_overdue", "bucket",
        ]

    def get_checklist_progress(self, obj):
        total = obj.checklist_items.count()
        if total == 0:
            return None
        done = obj.checklist_items.filter(is_completed=True).count()
        return {"done": done, "total": total}


class TaskDetailSerializer(serializers.ModelSerializer):
    """Full serializer for task detail view — includes nested relations."""
    assignees = UserSummarySerializer(many=True, read_only=True)
    labels = LabelSerializer(many=True, read_only=True)
    checklist_items = ChecklistItemSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "priority", "progress",
            "start_date", "due_date", "completed_at",
            "bucket", "created_by", "assignees", "labels",
            "checklist_items", "comments",
            "recurrence_rule", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "completed_at", "created_at", "updated_at"]


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    """Write serializer — accepts IDs for relations, not nested objects."""
    label_ids = serializers.PrimaryKeyRelatedField(
        queryset=Label.objects.all(), many=True, required=False, source="labels",
    )

    class Meta:
        model = Task
        fields = [
            "title", "description", "bucket", "priority",
            "start_date", "due_date", "label_ids", "recurrence_rule",
        ]

    def validate(self, data):
        start = data.get("start_date")
        due = data.get("due_date")
        if start and due and start > due:
            raise serializers.ValidationError(
                {"due_date": "Due date must be on or after start date."}
            )
        return data
```

```python
# apps/plans/api/serializers.py
from rest_framework import serializers

from plans.models import Bucket, Plan
from tasks.api.serializers import TaskListSerializer


class BucketSerializer(serializers.ModelSerializer):
    tasks = TaskListSerializer(many=True, read_only=True)

    class Meta:
        model = Bucket
        fields = ["id", "title", "color", "position", "tasks"]
        read_only_fields = ["id"]


class PlanListSerializer(serializers.ModelSerializer):
    total_tasks = serializers.IntegerField(read_only=True)
    completed_tasks = serializers.IntegerField(read_only=True)

    class Meta:
        model = Plan
        fields = ["id", "title", "description", "visibility", "total_tasks", "completed_tasks"]


class PlanDetailSerializer(serializers.ModelSerializer):
    buckets = BucketSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = ["id", "title", "description", "visibility", "team", "buckets", "created_at"]
        read_only_fields = ["id", "created_at"]
```

```python
# apps/accounts/api/serializers.py
from rest_framework import serializers

from accounts.models import User


class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal user representation for embedding in other serializers."""
    class Meta:
        model = User
        fields = ["id", "username", "display_name", "avatar"]
        read_only_fields = fields
```


## Views & ViewSets

### When to Use What

| Class | Use when | Planly example |
|---|---|---|
| `ModelViewSet` | Standard CRUD on a model | `TaskViewSet`, `PlanViewSet`, `CommentViewSet` |
| `mixins` + `GenericViewSet` | You need only some CRUD actions (e.g., list + create but not delete) | `LabelViewSet` (list + create, no destroy) |
| `APIView` | Non-CRUD endpoint, custom logic, or action that doesn't map to a model | Bucket reorder, bulk task assignment |
| `@action` decorator | Extra endpoint on an existing ViewSet | `TaskViewSet.assign`, `TaskViewSet.complete` |

### Planly ViewSets

```python
# apps/tasks/api/views.py
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from tasks.api.filters import TaskFilter
from tasks.api.permissions import IsTeamMember
from tasks.api.serializers import (
    ChecklistItemSerializer,
    CommentSerializer,
    TaskCreateUpdateSerializer,
    TaskDetailSerializer,
    TaskListSerializer,
)
from tasks.models import ChecklistItem, Comment, Task


class TaskViewSet(viewsets.ModelViewSet):
    """
    CRUD for tasks within a plan.

    list:    Lightweight task cards for board view.
    retrieve: Full task detail with nested comments, checklist, assignees.
    create:  Create a new task in a bucket.
    update:  Update task fields.
    destroy: Delete a task.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeamMember]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["priority", "due_date", "created_at"]

    def get_queryset(self):
        return (
            Task.objects
            .filter(bucket__plan__team__memberships__user=self.request.user)
            .select_related("bucket__plan")
            .prefetch_related("assignees", "labels", "checklist_items")
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return TaskListSerializer
        if self.action in ("create", "update", "partial_update"):
            return TaskCreateUpdateSerializer
        return TaskDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # ── Custom actions ───────────────────────────────────────

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark a task as completed."""
        task = self.get_object()
        task.mark_complete()
        return Response(TaskDetailSerializer(task).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """Assign users to a task. Body: {"user_ids": [1, 2]}"""
        task = self.get_object()
        user_ids = request.data.get("user_ids", [])
        from accounts.models import User
        from tasks.models import Assignment

        users = User.objects.filter(pk__in=user_ids)
        for user in users:
            Assignment.objects.get_or_create(
                task=task, user=user,
                defaults={"assigned_by": request.user},
            )
        return Response(TaskDetailSerializer(task).data)

    @action(detail=True, methods=["post"], url_path="comments")
    def add_comment(self, request, pk=None):
        """Add a comment to a task."""
        task = self.get_object()
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task, author=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="checklist")
    def add_checklist_item(self, request, pk=None):
        """Add a checklist item to a task."""
        task = self.get_object()
        serializer = ChecklistItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        position = task.checklist_items.count()
        serializer.save(task=task, position=position)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CommentViewSet(
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Update or delete a comment. Creation is via TaskViewSet.add_comment."""
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Comment.objects.filter(author=self.request.user)
```

```python
# apps/plans/api/views.py
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from plans.api.serializers import (
    BucketSerializer,
    PlanDetailSerializer,
    PlanListSerializer,
)
from plans.models import Bucket, Plan
from tasks.api.permissions import IsTeamMember


class PlanViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTeamMember]
    search_fields = ["title"]

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user).with_task_counts()

    def get_serializer_class(self):
        if self.action == "list":
            return PlanListSerializer
        return PlanDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="buckets/reorder")
    def reorder_buckets(self, request, pk=None):
        """Reorder buckets. Body: {"bucket_ids": [3, 1, 2]}"""
        plan = self.get_object()
        ordered_ids = request.data.get("bucket_ids", [])
        from plans.views_helpers import reorder_buckets
        reorder_buckets(plan, ordered_ids)
        return Response({"status": "ok"})
```


## Permissions

DRF's permission system is layered: global defaults in settings, per-view overrides, and custom permission classes.

### Custom Permissions for Planly

```python
# apps/tasks/api/permissions.py
from rest_framework import permissions


class IsTeamMember(permissions.BasePermission):
    """User must be a member of the team that owns the plan."""

    def has_object_permission(self, request, view, obj):
        # Determine the plan from the object
        if hasattr(obj, "bucket"):
            plan = obj.bucket.plan  # Task
        elif hasattr(obj, "plan"):
            plan = obj.plan         # Bucket
        elif hasattr(obj, "team"):
            plan = obj              # Plan
        else:
            return False

        team = plan.team if hasattr(plan, "team") else plan
        return team.memberships.filter(user=request.user).exists()


class IsCommentAuthor(permissions.BasePermission):
    """Only the comment author can edit or delete it."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user
```


## Filtering

Use `django-filter` for declarative, reusable filter sets:

```python
# apps/tasks/api/filters.py
import django_filters

from tasks.models import Task


class TaskFilter(django_filters.FilterSet):
    bucket = django_filters.NumberFilter(field_name="bucket_id")
    plan = django_filters.NumberFilter(field_name="bucket__plan_id")
    assignee = django_filters.NumberFilter(field_name="assignments__user_id")
    priority = django_filters.ChoiceFilter(choices=Task.Priority.choices)
    progress = django_filters.ChoiceFilter(choices=Task.Progress.choices)
    overdue = django_filters.BooleanFilter(method="filter_overdue")
    due_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    due_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")

    class Meta:
        model = Task
        fields = ["bucket", "plan", "assignee", "priority", "progress"]

    def filter_overdue(self, queryset, name, value):
        if value:
            return queryset.overdue()
        return queryset
```


## URL Routing

### Versioned API URLs

Use URL-path versioning (`/api/v1/`) — it's explicit, cacheable, and easy to reason about:

```python
# apps/tasks/api/urls.py
from rest_framework.routers import DefaultRouter

from tasks.api import views

router = DefaultRouter()
router.register(r"tasks", views.TaskViewSet, basename="task")
router.register(r"comments", views.CommentViewSet, basename="comment")

urlpatterns = router.urls
```

```python
# apps/plans/api/urls.py
from rest_framework.routers import DefaultRouter

from plans.api import views

router = DefaultRouter()
router.register(r"plans", views.PlanViewSet, basename="plan")

urlpatterns = router.urls
```

```python
# config/urls.py
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # Server-rendered views
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("plans/", include("plans.urls", namespace="plans")),
    path("tasks/", include("tasks.urls", namespace="tasks")),
    path("attachments/", include("attachments.urls", namespace="attachments")),
    path("notifications/", include("notifications.urls", namespace="notifications")),

    # API v1
    path("api/v1/", include("plans.api.urls")),
    path("api/v1/", include("tasks.api.urls")),
    path("api/v1/", include("accounts.api.urls")),

    # API auth (JWT)
    path("api/v1/auth/", include("rest_framework_simplejwt.urls")),

    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-redoc"),
]
```

### What the Router Generates

`DefaultRouter` for `TaskViewSet` produces these URLs:

| URL | Method | Action | Name |
|-----|--------|--------|------|
| `/api/v1/tasks/` | GET | list | `task-list` |
| `/api/v1/tasks/` | POST | create | `task-list` |
| `/api/v1/tasks/{pk}/` | GET | retrieve | `task-detail` |
| `/api/v1/tasks/{pk}/` | PUT | update | `task-detail` |
| `/api/v1/tasks/{pk}/` | PATCH | partial_update | `task-detail` |
| `/api/v1/tasks/{pk}/` | DELETE | destroy | `task-detail` |
| `/api/v1/tasks/{pk}/complete/` | POST | complete | `task-complete` |
| `/api/v1/tasks/{pk}/assign/` | POST | assign | `task-assign` |
| `/api/v1/tasks/{pk}/comments/` | POST | add_comment | `task-add-comment` |
| `/api/v1/tasks/{pk}/checklist/` | POST | add_checklist_item | `task-add-checklist-item` |


## Authentication

### JWT (Recommended for APIs)

Planly uses `djangorestframework-simplejwt` for stateless token authentication:

```bash
pip install djangorestframework-simplejwt
```

The JWT endpoints are included in `config/urls.py` above. They provide:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/token/` | POST | Obtain access + refresh token pair |
| `/api/v1/auth/token/refresh/` | POST | Refresh an expired access token |
| `/api/v1/auth/token/verify/` | POST | Verify a token is still valid |

Clients include the access token in every request:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Session Authentication (For Browsable API)

DRF's `SessionAuthentication` is included alongside JWT in the settings. This lets developers use the browsable API at `/api/v1/` while logged into the Django admin — useful during development but not for production API consumers.

### Per-View Authentication Overrides

Some endpoints may need different auth. Use the `authentication_classes` attribute:

```python
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

class PublicPlanListView(APIView):
    """Public plans don't require authentication."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        plans = Plan.objects.filter(visibility=Plan.Visibility.PUBLIC)
        serializer = PlanListSerializer(plans, many=True)
        return Response(serializer.data)
```


## CORS

When Planly's API is consumed by a separate frontend (a React or mobile app), CORS must be configured:

```bash
pip install django-cors-headers
```

```python
# config/settings/production.py
INSTALLED_APPS += ["corsheaders"]

MIDDLEWARE.insert(0, "corsheaders.middleware.CorsMiddleware")

# Lock down to specific origins — never use CORS_ALLOW_ALL_ORIGINS in production
CORS_ALLOWED_ORIGINS = [
    "https://app.planly.example.com",
    "https://mobile.planly.example.com",
]

# If cookies are needed (e.g., session auth alongside JWT)
CORS_ALLOW_CREDENTIALS = True

# Expose pagination headers to the client
CORS_EXPOSE_HEADERS = ["X-Total-Count"]
```


## API Documentation with drf-spectacular

`drf-spectacular` generates an OpenAPI 3 schema from your serializers, views, and type hints. It replaces the deprecated built-in DRF schema generation and the older `drf-yasg`.

### Setup

Already configured in the settings above. The three documentation endpoints are:

| URL | Purpose |
|-----|---------|
| `/api/schema/` | Raw OpenAPI JSON/YAML schema (for client generation) |
| `/api/docs/` | Swagger UI (interactive, try-it-out) |
| `/api/redoc/` | ReDoc (clean, readable) |

### Customizing with `@extend_schema`

When the auto-generated schema isn't accurate enough, use the `@extend_schema` decorator:

```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample


class TaskViewSet(viewsets.ModelViewSet):
    # ...

    @extend_schema(
        summary="Mark task complete",
        description="Sets progress to 100% and records the completion timestamp.",
        responses={200: TaskDetailSerializer},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.mark_complete()
        return Response(TaskDetailSerializer(task).data)

    @extend_schema(
        summary="Assign users to task",
        request={"application/json": {"type": "object", "properties": {
            "user_ids": {"type": "array", "items": {"type": "integer"}},
        }}},
        responses={200: TaskDetailSerializer},
        examples=[
            OpenApiExample(
                "Assign two users",
                value={"user_ids": [1, 2]},
                request_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        # ...
```

### Validate Your Schema in CI

Add a schema validation step to catch drift between code and documentation:

```bash
python manage.py spectacular --validate --fail-on-warn
```


## REST Design Standards

### URL Conventions

Use plural nouns, not verbs. Actions on a resource use nested paths or custom actions:

```
# GOOD
GET    /api/v1/plans/              → list plans
POST   /api/v1/plans/              → create plan
GET    /api/v1/plans/42/           → retrieve plan 42
PATCH  /api/v1/plans/42/           → update plan 42
DELETE /api/v1/plans/42/           → delete plan 42
POST   /api/v1/tasks/99/complete/  → custom action: complete task 99

# BAD
GET    /api/v1/getPlans/
POST   /api/v1/createTask/
POST   /api/v1/completeTask/99/
```

### HTTP Status Codes

Use the right status codes consistently:

| Code | Meaning | Planly usage |
|------|---------|-------------|
| `200` | OK | Successful GET, PUT, PATCH |
| `201` | Created | Successful POST that creates a resource |
| `204` | No Content | Successful DELETE |
| `400` | Bad Request | Validation errors (serializer.is_valid() failed) |
| `401` | Unauthorized | Missing or invalid auth token |
| `403` | Forbidden | Authenticated but no permission (not a team member) |
| `404` | Not Found | Resource doesn't exist or user lacks access |
| `429` | Too Many Requests | Throttle limit exceeded |

### Response Envelope

DRF's default pagination wraps list responses automatically:

```json
{
    "count": 142,
    "next": "https://planly.example.com/api/v1/tasks/?page=2",
    "previous": null,
    "results": [
        {"id": 1, "title": "Fix login page", "priority": 1, ...},
        {"id": 2, "title": "Update onboarding flow", "priority": 5, ...}
    ]
}
```

For non-paginated responses, return the object directly — no wrapper:

```json
{"id": 1, "title": "Fix login page", "priority": 1, "description": "..."}
```

### Error Response Format

DRF returns structured errors by default. Keep this format consistent:

```json
{
    "title": ["This field may not be blank."],
    "due_date": ["Due date must be on or after start date."]
}
```

For non-field errors:

```json
{
    "detail": "You do not have permission to perform this action."
}
```

### Versioning Strategy

Planly uses URL path versioning (`/api/v1/`). When a breaking change is needed:

1. Create `/api/v2/` endpoints alongside v1.
2. Deprecate v1 with a sunset header and documentation notice.
3. Give consumers a migration window (minimum 6 months for production APIs).
4. Remove v1 after the window closes.

Non-breaking changes (new fields, new endpoints) go into the existing version without bumping.


## Testing API Endpoints

Use DRF's `APIClient` for clean, readable tests:

```python
# apps/tasks/tests/test_api.py
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import MembershipFactory, UserFactory
from plans.tests.factories import BucketFactory
from tasks.tests.factories import TaskFactory


@pytest.mark.django_db
class TestTaskAPI:
    def setup_method(self):
        self.client = APIClient()
        self.membership = MembershipFactory()
        self.user = self.membership.user
        self.plan = self.membership.team.plans.first()
        self.client.force_authenticate(user=self.user)

    def test_list_tasks(self):
        bucket = BucketFactory(plan=self.plan)
        TaskFactory.create_batch(3, bucket=bucket)

        response = self.client.get("/api/v1/tasks/", {"plan": self.plan.pk})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_create_task(self):
        bucket = BucketFactory(plan=self.plan)

        response = self.client.post("/api/v1/tasks/", {
            "title": "New task",
            "bucket": bucket.pk,
            "priority": 5,
        })

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New task"

    def test_complete_task(self):
        bucket = BucketFactory(plan=self.plan)
        task = TaskFactory(bucket=bucket)

        response = self.client.post(f"/api/v1/tasks/{task.pk}/complete/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["progress"] == 100

    def test_non_member_cannot_access(self):
        outsider = UserFactory()
        self.client.force_authenticate(user=outsider)

        response = self.client.get("/api/v1/tasks/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0  # queryset scoped to teams


@pytest.mark.django_db
class TestTaskAPIValidation:
    def setup_method(self):
        self.client = APIClient()
        self.membership = MembershipFactory()
        self.client.force_authenticate(user=self.membership.user)

    def test_start_after_due_rejected(self):
        bucket = BucketFactory(plan=self.membership.team.plans.first())

        response = self.client.post("/api/v1/tasks/", {
            "title": "Bad dates",
            "bucket": bucket.pk,
            "priority": 5,
            "start_date": "2026-06-01",
            "due_date": "2026-05-01",
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "due_date" in response.data
```


## Checklist

1. **Keep API code in `api/` subpackages** — don't mix DRF serializers and views with server-rendered forms and views.
2. **Use separate serializers for list, detail, and create/update** — list serializers are lightweight; detail serializers are comprehensive; write serializers validate input.
3. **Never use `fields = "__all__"`** — explicitly list every field to avoid accidental exposure.
4. **Scope querysets to the current user** in `get_queryset()` — this is your primary access control layer.
5. **Use `@action` for non-CRUD operations** — `complete`, `assign`, `reorder` are actions, not separate views.
6. **Configure throttling** — set different rates for anonymous and authenticated users.
7. **Use `drf-spectacular`** for API documentation — validate the schema in CI with `--validate --fail-on-warn`.
8. **Version your API** with URL path prefixes (`/api/v1/`) — never break existing consumers without a migration window.
9. **Use JWT for stateless API auth** and session auth only for the browsable API during development.
10. **Test every endpoint** — status codes, permissions, validation errors, and edge cases.



---

# 14. Full-Text Search

## Why Postgres Full-Text Search

Planly needs to search across tasks (title, description), comments (body), and plans (title, description). Users type into a search bar on the board and expect instant, relevant results — partial matches, stemming ("running" matches "run"), and ranking by relevance.

PostgreSQL's built-in full-text search handles all of this without adding Elasticsearch or any external service. It supports lexeme-based stemming, weighted ranking (title matches score higher than description matches), and GIN indexes for fast lookups. For a project like Planly — thousands to low millions of tasks — this is more than enough.


## Two-Tier Approach

Planly uses two levels of full-text search depending on complexity:

| Tier | Method | Use when | Planly example |
|------|--------|----------|----------------|
| **Tier 1** | `GeneratedField` | Searching columns on the same table, no weights needed | Plans searched by title + description |
| **Tier 2** | `django-pgtrigger` with Postgres triggers | You need weighted ranking (title > description), OR you need to search across related model fields | Tasks searched by title (weight A) + description (weight B) + comment text (weight C) |

Start with Tier 1 — it's zero dependencies, zero triggers, and fully managed by Django migrations. Upgrade to Tier 2 when you hit its limitations.


## Installation

Tier 1 requires no extra packages — just `django.contrib.postgres` (already in most Django projects).

Tier 2 requires `django-pgtrigger`:

```bash
pip install django-pgtrigger
```

```python
# config/settings/base.py
INSTALLED_APPS = [
    # ...
    "pgtrigger",               # only needed for Tier 2
    "django.contrib.postgres",  # required for SearchVectorField
    # ...
]
```


## Tier 1: `GeneratedField` (Zero Dependencies)

Django's `GeneratedField` (introduced in 5.0) creates a `GENERATED ALWAYS AS ... STORED` column in PostgreSQL. The database computes and stores the tsvector automatically on every INSERT and UPDATE — no triggers, no signals, no application code.

### Adding Search to Plans

Plans are searched by title and description with equal weight — a perfect fit for `GeneratedField`:

```python
# apps/plans/models.py
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models

from core.models import TimeStampedModel


class Plan(TimeStampedModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # ... other fields from Section 3 ...

    # Full-text search — computed and stored by Postgres, no trigger needed
    search_vector = models.GeneratedField(
        expression=SearchVector("title", "description", config="english"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"], name="idx_plan_search"),
        ]
```

That's it. Run `makemigrations` and `migrate`. The column is always in sync because the database engine recomputes it on every write — ORM saves, raw SQL, bulk operations, data migrations. No backfill migration is needed because existing rows are computed automatically.

### Querying

```python
# apps/plans/managers.py
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import models


class PlanQuerySet(models.QuerySet):
    # ... existing methods from Section 3 ...

    def search(self, query_text):
        """Full-text search across plan title and description."""
        if not query_text:
            return self.none()

        query = SearchQuery(query_text, config="english", search_type="websearch")
        return (
            self.filter(search_vector=query)
            .annotate(search_rank=SearchRank("search_vector", query))
            .order_by("-search_rank")
        )
```

The `search_type="websearch"` option lets users type natural queries like `sprint planning Q3` or `"exact phrase" -excluded` — Postgres parses this into the appropriate tsquery automatically.

### When to Stay on Tier 1

`GeneratedField` is the right choice when:

- You're searching columns **on the same table** (no joins needed).
- You don't need **weighted ranking** (title matches ranking higher than description matches).
- You want **zero dependencies** and fully managed migrations.

For Planly, this covers plan search completely. Labels and buckets are short-text models that don't need full-text search at all.

### Limitations That Push You to Tier 2

- **No `setweight()`** — The `to_tsvector` expression Postgres generates from `GeneratedField` is considered mutable when weights are involved, causing `ProgrammingError: generation expression is not immutable`.
- **No cross-table references** — `GeneratedField` can only reference columns on the same table. You can't include comment text or assignee names in a task's search vector.
- **No custom trigger logic** — You can't run arbitrary PL/pgSQL when the row changes.

When you hit any of these, move to Tier 2.


## Tier 2: Postgres Triggers with `django-pgtrigger`

Tasks are Planly's most complex search target. Users expect a search for "login bug" to match tasks where "login" is in the title and "bug" is in a comment. Title matches should rank higher than description matches, which should rank higher than comment matches. This requires weighted search across related models — exactly what `GeneratedField` can't do.

### Step 1: Add the SearchVectorField

```python
# apps/tasks/models.py
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from core.models import TimeStampedModel


class Task(TimeStampedModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # ... other fields from Section 3 ...

    # Full-text search — populated by Postgres triggers
    search_vector = SearchVectorField(null=True)

    class Meta:
        indexes = [
            # ... existing indexes from Section 3 ...
            GinIndex(fields=["search_vector"], name="idx_task_search"),
        ]
```

### Step 2: Create the Trigger for Same-Table Fields

For the basic case (title + description, weighted, no related models), use a custom `pgtrigger.Trigger`:

```python
# apps/tasks/models.py
import pgtrigger


class Task(TimeStampedModel):
    # ... fields and search_vector from above ...

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"], name="idx_task_search"),
        ]
        triggers = [
            pgtrigger.Trigger(
                name="task_search_vector_update",
                when=pgtrigger.Before,
                operation=pgtrigger.Insert | pgtrigger.UpdateOf("title", "description"),
                func=pgtrigger.Func(
                    """
                    NEW.search_vector :=
                        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B');
                    RETURN NEW;
                    """
                ),
            ),
        ]
```

This trigger fires before every INSERT or UPDATE that touches `title` or `description`. It assigns weight A to the title and weight B to the description, so a search for "onboarding" ranks a task titled "Onboarding flow" above a task where "onboarding" only appears in the description.

Run `makemigrations` and `migrate` — `django-pgtrigger` generates the migration automatically.

### Step 3: Include Related Model Fields (Comments)

This is where triggers shine and `GeneratedField` can't follow. When a user adds a comment to a task, we want the task's search vector to include that comment text (with a lower weight). This requires a trigger on the `Comment` model that updates the *parent task's* search vector.

Create a custom migration with raw SQL for the cross-table trigger:

```python
# apps/tasks/migrations/0006_comment_search_trigger.py
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0005_task_search_vector"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Function: recompute a task's search vector including its comments
                CREATE OR REPLACE FUNCTION recompute_task_search_vector()
                RETURNS trigger AS $$
                BEGIN
                    UPDATE tasks_task SET search_vector =
                        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
                        setweight(
                            coalesce(
                                (SELECT string_agg(body, ' ')
                                 FROM tasks_comment
                                 WHERE task_id = tasks_task.id),
                                ''
                            )::tsvector,
                            'C'
                        )
                    WHERE id = COALESCE(NEW.task_id, OLD.task_id);
                    RETURN NEW;
                END $$ LANGUAGE plpgsql;

                -- Trigger: fires when a comment is added, updated, or deleted
                CREATE TRIGGER comment_updates_task_search
                    AFTER INSERT OR UPDATE OF body OR DELETE
                    ON tasks_comment
                    FOR EACH ROW EXECUTE FUNCTION recompute_task_search_vector();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS comment_updates_task_search ON tasks_comment;
                DROP FUNCTION IF EXISTS recompute_task_search_vector();
            """,
        ),
    ]
```

Now update the task-level trigger to also incorporate comments when the task's own fields change:

```python
# apps/tasks/models.py — updated trigger
class Task(TimeStampedModel):
    # ... fields ...

    class Meta:
        triggers = [
            pgtrigger.Trigger(
                name="task_search_vector_update",
                when=pgtrigger.Before,
                operation=pgtrigger.Insert | pgtrigger.UpdateOf("title", "description"),
                func=pgtrigger.Func(
                    """
                    NEW.search_vector :=
                        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
                        setweight(
                            to_tsvector(
                                'english',
                                coalesce(
                                    (SELECT string_agg(body, ' ')
                                     FROM tasks_comment
                                     WHERE task_id = NEW.id),
                                    ''
                                )
                            ),
                            'C'
                        );
                    RETURN NEW;
                    """
                ),
            ),
        ]
```

With both triggers in place, the search vector stays current regardless of whether the task's own fields change or a comment is added/edited/deleted.

### Step 4: Backfill Existing Data

Triggers only fire on future writes. Backfill existing rows:

```python
# apps/tasks/migrations/0007_backfill_task_search_vector.py
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0006_comment_search_trigger"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE tasks_task SET search_vector =
                    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                    setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
                    setweight(
                        to_tsvector(
                            'english',
                            coalesce(
                                (SELECT string_agg(body, ' ')
                                 FROM tasks_comment
                                 WHERE task_id = tasks_task.id),
                                ''
                            )
                        ),
                        'C'
                    );
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
```

### Step 5: Query with SearchQuery and SearchRank

```python
# apps/tasks/managers.py
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import models


class TaskQuerySet(models.QuerySet):
    # ... existing methods from Section 3 ...

    def search(self, query_text):
        """
        Full-text search across task title, description, and comments.
        Results ranked by relevance — title matches rank highest.
        """
        if not query_text:
            return self.none()

        query = SearchQuery(query_text, config="english", search_type="websearch")
        return (
            self.filter(search_vector=query)
            .annotate(search_rank=SearchRank("search_vector", query))
            .order_by("-search_rank")
        )
```

`SearchRank` automatically respects the A/B/C weights set by the trigger.


## Using Search in Views

### Server-Rendered View

```python
# apps/tasks/views.py
from django.shortcuts import render

from tasks.models import Task


def search_tasks(request):
    query = request.GET.get("q", "").strip()
    results = Task.objects.for_user(request.user).search(query) if query else []

    return render(request, "tasks/search_results.html", {
        "query": query,
        "results": results,
    })
```

### API Endpoint (DRF)

```python
# apps/tasks/api/views.py
from rest_framework.decorators import action
from rest_framework.response import Response


class TaskViewSet(viewsets.ModelViewSet):
    # ... existing from Section 13 ...

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Full-text search: GET /api/v1/tasks/search/?q=login+bug"""
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"results": []})

        tasks = self.get_queryset().search(query)[:50]
        serializer = TaskListSerializer(tasks, many=True)
        return Response({"results": serializer.data})
```


## Searching Across Multiple Models

Planly's global search bar searches tasks and plans simultaneously. Since they use different search tiers (tasks use Tier 2, plans use Tier 1), combine results in the view:

```python
# apps/core/views.py
from itertools import chain

from django.shortcuts import render

from plans.models import Plan
from tasks.models import Task


def global_search(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return render(request, "core/search_results.html", {"results": []})

    tasks = (
        Task.objects.for_user(request.user)
        .search(query)[:20]
        .values_list("pk", "title", "search_rank")
    )
    plans = (
        Plan.objects.for_user(request.user)
        .search(query)[:10]
        .values_list("pk", "title", "search_rank")
    )

    results = sorted(
        chain(
            [{"type": "task", "pk": pk, "title": t, "rank": r} for pk, t, r in tasks],
            [{"type": "plan", "pk": pk, "title": t, "rank": r} for pk, t, r in plans],
        ),
        key=lambda x: x["rank"],
        reverse=True,
    )

    return render(request, "core/search_results.html", {
        "query": query,
        "results": results[:25],
    })
```


## SearchHeadline — Highlighting Matches

Show users where their query matched by using `SearchHeadline`:

```python
from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank


def search_tasks(request):
    query_text = request.GET.get("q", "").strip()
    if not query_text:
        return render(request, "tasks/search_results.html", {"results": []})

    query = SearchQuery(query_text, config="english", search_type="websearch")
    results = (
        Task.objects.for_user(request.user)
        .filter(search_vector=query)
        .annotate(
            search_rank=SearchRank("search_vector", query),
            headline=SearchHeadline(
                "description",
                query,
                config="english",
                start_sel="<mark>",
                stop_sel="</mark>",
                max_words=35,
                min_words=15,
            ),
        )
        .order_by("-search_rank")[:25]
    )

    return render(request, "tasks/search_results.html", {
        "query": query_text,
        "results": results,
    })
```

In the template, render the headline with `|safe` since it contains HTML:

```html
{% for task in results %}
<div class="search-result">
    <h4><a href="{% url 'tasks:task-detail' task.pk %}">{{ task.title }}</a></h4>
    <p>{{ task.headline|safe }}</p>
</div>
{% endfor %}
```


## Managing Triggers (Tier 2)

`django-pgtrigger` provides management commands for inspecting and controlling triggers:

```bash
# List all triggers and their status
python manage.py pgtrigger ls

# Reinstall triggers (useful after manual DB changes)
python manage.py pgtrigger install

# Temporarily disable triggers (e.g., during a bulk import)
python manage.py pgtrigger disable tasks.Task:task_search_vector_update

# Re-enable
python manage.py pgtrigger enable tasks.Task:task_search_vector_update
```

For bulk imports where you want to skip the trigger overhead and backfill once at the end:

```python
import pgtrigger

# Disable the trigger for this thread
with pgtrigger.ignore("tasks.Task:task_search_vector_update"):
    Task.objects.bulk_create(large_list_of_tasks)

# Backfill search vectors in one pass
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        UPDATE tasks_task SET search_vector =
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'B')
        WHERE search_vector IS NULL;
    """)
```


## Decision Guide: Which Tier?

```
Do you need weighted ranking (title > description)?
├── No  → Tier 1: GeneratedField
└── Yes → Tier 2: pgtrigger

Do you need to search across related models (e.g., task + its comments)?
├── No  → Tier 1: GeneratedField
└── Yes → Tier 2: pgtrigger (with a cross-table trigger via RunSQL)

Do you want zero third-party dependencies for search?
├── Yes → Tier 1: GeneratedField (or raw RunSQL triggers if you need Tier 2 features)
└── No  → Tier 2: pgtrigger for managed trigger lifecycle
```

Planly uses both tiers side by side — `GeneratedField` for plans, `django-pgtrigger` for tasks. This is the recommended approach: start with the simplest tool that solves the problem, and escalate only when the requirements demand it.


## When to Reach for Elasticsearch

Postgres full-text search covers the majority of use cases. Consider an external search engine (Elasticsearch, Meilisearch, Typesense) only when you need:

- **Fuzzy matching and typo tolerance** — Postgres FTS is lexeme-based and doesn't handle "assgnee" → "assignee".
- **Faceted search** — filtering by multiple dimensions with counts (e.g., "15 tasks in Urgent, 8 in To Do").
- **Cross-database search** — searching data that lives outside PostgreSQL.
- **Massive scale** — billions of documents where GIN index rebuild times become a bottleneck.

For Planly's scale and requirements, Postgres is the right choice. It's zero additional infrastructure, zero sync lag, and fully transactional — the search results are always consistent with the data.


## Checklist

1. **Start with `GeneratedField` (Tier 1)** — zero dependencies, fully managed, always in sync. Use for same-table, unweighted search.
2. **Upgrade to `django-pgtrigger` (Tier 2)** when you need weighted ranking or cross-table search (related model fields).
3. **Use `SearchVectorField` with a GIN index** — never compute tsvectors at query time on large tables.
4. **Use `search_type="websearch"`** in `SearchQuery` — it parses natural user queries including quoted phrases and negation.
5. **Use `SearchRank` for ordering** — results sorted by relevance, not by creation date.
6. **Use `SearchHeadline` for result snippets** — show users where their query matched.
7. **Always backfill existing data** when using triggers (Tier 2) — the trigger only fires on future writes. `GeneratedField` (Tier 1) handles this automatically.
8. **Use raw `RunSQL` for cross-table triggers** — `pgtrigger.Trigger` manages same-table triggers; comment→task cross-table triggers need a migration with raw SQL and a reverse.
9. **Use `pgtrigger ls`** to verify triggers are installed and up to date after deployments.
10. **Stay with Postgres** until you genuinely need fuzzy matching, faceting, or billion-document scale.
