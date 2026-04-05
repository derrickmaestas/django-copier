---
name: django
description: Django 6+ best practices, conventions, and implementation patterns for building modern Python web applications with PostgreSQL. Use this skill whenever working with Django — defining models, writing views, configuring URLs, creating forms, building templates, writing tests, setting up background tasks, or any task involving Django and its ecosystem (DRF, pytest-django, factory_boy, HTMX, Ruff, ty). Always use this skill when you see Django imports, `models.Model` subclasses, `urlpatterns`, `INSTALLED_APPS`, template tags, or management commands, even if the user doesn't explicitly mention Django.
---

# Django

Best practices and patterns for Django 6+, Python 3.14+, and PostgreSQL.

## Tooling

| Tool | Purpose |
|------|---------|
| **uv** | Package management — not pip, not poetry |
| **ruff** | Linting and formatting |
| **ty** | Type checking |
| **Docker** | Multi-stage builds using `debian:trixie-slim` + uv-managed Python (not the official `python:3.14-slim-trixie` image — decouples OS from Python, faster runtime) |
| **docker compose watch** | Development file syncing (not bind mounts) |
| **django-storages[s3]** | Production file storage (S3/S3-compatible). Dev can use local filesystem or MinIO |

## Project Layout

Use `config/` for the Django project package (not a project-named directory) and `apps/` for all first-party apps. `apps/` is a Python package (`__init__.py` present). Apps are registered in `INSTALLED_APPS` with the `apps.*` prefix (e.g., `"apps.core"`, `"apps.accounts"`), and each `AppConfig` sets a short `label` to keep database table names clean.

Entry points (`manage.py`, `wsgi.py`, `asgi.py`) add `apps/` to `sys.path` so that internal cross-app imports can use the `apps.*` prefix:

```python
# manage.py
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "apps"))
```

### Import conventions

- **Top-level imports only.** Never use local/inline imports unless absolutely necessary to avoid circular imports.
- **Within app source code** — use relative imports: `from .models import Plan`, `from .signals import notify`
- **In tests** — use absolute imports: `from apps.accounts.models import User`, `from apps.accounts.tests.factories import UserFactory`
- **Across apps** — use absolute imports: `from apps.core.models import TimeStampedModel`
- **`django.tasks` alias** — import as `django_tasks` to avoid confusion with the `apps.tasks` app: `from django.tasks import task as django_task`

```
planly/                      # repo root
├── config/                  # project config (settings, urls, wsgi, asgi)
│   ├── settings/
│   │   ├── __init__.py      # empty — each entry point sets DJANGO_SETTINGS_MODULE directly
│   │   ├── base.py
│   │   ├── local.py
│   │   ├── production.py
│   │   └── test.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/                    # all first-party apps (Python package with __init__.py)
│   ├── __init__.py
│   ├── core/                # abstract base models, middleware, template tags — no tables
│   ├── accounts/            # custom user, teams, membership
│   ├── plans/               # plans (boards), buckets (columns)
│   ├── tasks/               # tasks, assignments, checklists, labels, comments
│   ├── attachments/         # file uploads
│   └── notifications/       # in-app and email notifications
├── templates/               # project-level templates (base.html, partials, error pages)
├── static/                  # project-level static files
├── manage.py
├── pyproject.toml
├── Dockerfile
├── compose.yaml
├── compose.override.yaml    # development (auto-loaded)
└── compose.prod.yaml
```

Each app follows a consistent internal structure:

```
apps/<app>/
├── models.py
├── managers.py         # custom QuerySets
├── views.py            # server-rendered views
├── urls.py
├── forms.py
├── signals.py          # connected in AppConfig.ready()
├── tasks.py            # Django 6 background tasks
├── admin.py
├── apps.py
├── api/                # DRF layer (when needed)
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── permissions.py
│   └── filters.py
├── tests/
│   ├── test_models.py
│   ├── test_views.py
│   ├── test_api.py
│   └── factories.py   # factory_boy
├── templates/<app>/    # namespaced templates
└── migrations/
```

## Naming Conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| App names | Short, lowercase, plural where natural | `accounts`, `plans`, `tasks`, `notifications` |
| Model classes | PascalCase, singular | `Plan`, `Bucket`, `Task`, `ChecklistItem` |
| Model fields | snake_case, no redundant prefixes | `title`, `due_date`, `created_at` — not `task_title` on a `Task` |
| FK / M2M fields | Named for the related concept | `bucket` (FK), `assignees` (M2M), `created_by` (FK to User) |
| URL names | Namespaced with app, hyphen-separated | `plans:plan-board`, `tasks:task-detail` |
| Template files | snake_case, under `<app_name>/` | `plans/plan_board.html`, `tasks/task_card.html` |
| Management commands | snake_case verbs | `recur_tasks`, `send_daily_digests` |
| Settings constants | UPPER_SNAKE_CASE | `DATABASE_URL`, `PLANLY_MAX_ATTACHMENT_SIZE_MB` |
| Test files | `test_<module>.py` | `test_models.py`, `test_views.py`, `test_tasks.py` |
| Test classes | `Test*` prefix, PascalCase | `TestSettings`, `TestPlanModel`, `TestTaskCreateView` |
| Test functions | `test_*` prefix, snake_case | `test_django_settings_loaded`, `test_create_task` |
| Factories | `<Model>Factory` | `PlanFactory`, `BucketFactory`, `TaskFactory` |

## When to Create a New App

Create a new app when the domain concept has its own models, its own business logic, and could be removed or replaced without rewriting everything else. Don't create an app for a single utility model, a set of template tags, or a feature that only modifies an existing app's behavior.

Heuristic: if the app would have fewer than two models and no views of its own, it probably doesn't need to be a separate app. `Label` and `ChecklistItem` live inside `tasks` — they only make sense in the context of a task.

## Split Settings

Settings are split into environment-specific modules. Each entry point sets `DJANGO_SETTINGS_MODULE` to the correct module directly — no router in `__init__.py`:

```python
# manage.py (local development)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

# config/wsgi.py and config/asgi.py (production)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

# pyproject.toml (tests)
# [tool.pytest.ini_options]
# DJANGO_SETTINGS_MODULE = "config.settings.test"
```

`config/settings/__init__.py` is **empty**. This avoids the indirection of a `DJANGO_ENV` router — each entry point declares exactly which settings it uses, and `DJANGO_SETTINGS_MODULE` can always be overridden from the environment when needed (e.g., `DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check`).

| Module | Key characteristics |
|--------|-------------------|
| `base.py` | Shared: apps, middleware, database, templates, auth, `AUTH_USER_MODEL`, `TASKS` |
| `local.py` | `DEBUG=True`, debug-toolbar, console email, `ImmediateBackend` for tasks |
| `production.py` | Security headers, CSP, whitenoise, Redis cache, SMTP email, `DatabaseBackend` |
| `test.py` | MD5 password hasher, locmem email, `DummyBackend` for tasks, temp `MEDIA_ROOT` |

Entry points and their default settings modules:

| Entry point | Default module | Used by |
|-------------|---------------|---------|
| `manage.py` | `config.settings.local` | Local development, management commands |
| `config/wsgi.py` | `config.settings.production` | Gunicorn in production |
| `config/asgi.py` | `config.settings.production` | ASGI server in production |
| `pyproject.toml` | `config.settings.test` | pytest |

App-specific settings are prefixed with the project name to avoid collisions:

```python
# config/settings/base.py
PLANLY_MAX_ATTACHMENT_SIZE_MB = int(os.environ.get("PLANLY_MAX_ATTACHMENT_SIZE_MB", "25"))
```

## Models

### Abstract Base Models

The `core` app provides abstract bases — no tables, no views, no URLs:

```python
# apps/core/models.py
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrderedModel(models.Model):
    position = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["position"]
```

### Field Rules

| Field type | Optional means | Use |
|---|---|---|
| `CharField`, `TextField` | Empty string | `blank=True` only — **never** `null=True` |
| `DateField`, `DateTimeField` | No value | `null=True, blank=True` |
| `IntegerField`, numbers | No value | `null=True, blank=True` |
| `BooleanField` | Always True/False | `default=` — never nullable unless three-state is needed |
| `ForeignKey` (optional) | Relationship absent | `null=True, blank=True` |
| `ManyToManyField` | Zero selections | `blank=True` only — **never** `null` |
| `JSONField` | No data | Prefer `default=dict` over `null=True` |

### Choices

Use `IntegerChoices` for ordered values (priority, progress) and `TextChoices` for categorical labels (role, visibility). Leave gaps between integer values for future insertions:

```python
class Priority(models.IntegerChoices):
    URGENT = 1, "Urgent"
    IMPORTANT = 3, "Important"
    MEDIUM = 5, "Medium"
    LOW = 9, "Low"
```

### Constraints and Indexes

Use `Meta.indexes` with explicit names (not `db_index=True`) and `UniqueConstraint` (not `unique_together`). Use `Deferrable.DEFERRED` on position uniqueness constraints to support drag-and-drop reordering:

```python
class Bucket(TimeStampedModel, OrderedModel):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="buckets")
    title = models.CharField(max_length=255)

    class Meta(OrderedModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "position"],
                name="unique_bucket_position",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]
        indexes = [
            models.Index(fields=["plan", "position"], name="idx_bucket_plan_pos"),
        ]
```

### `on_delete` Strategy

| Strategy | When to use |
|---|---|
| `CASCADE` | Child has no meaning without parent (Bucket→Plan, Task→Bucket) |
| `SET_NULL` | Child survives parent deletion (Task.created_by → User). Requires `null=True`. |
| `PROTECT` | Deletion would be destructive and must be prevented (Team.owner) |

### Custom Managers and QuerySets

Put query logic on custom QuerySets, not in views. Wire up with `as_manager()`:

```python
# apps/tasks/managers.py
class TaskQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(assignments__user=user)

    def overdue(self):
        return self.filter(due_date__lt=timezone.now().date(), progress__lt=100)

    def with_counts(self):
        return self.annotate(
            checklist_total=models.Count("checklist_items"),
            checklist_done=models.Count(
                "checklist_items", filter=models.Q(checklist_items__is_completed=True)
            ),
        )

# apps/tasks/models.py
class Task(TimeStampedModel):
    objects = TaskQuerySet.as_manager()
```

### Fat Models

Domain logic belongs on the model. Views call methods, not compute things:

```python
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

### Signals

Define in `signals.py`, connect in `AppConfig.ready()`. Never put signal handlers in `models.py`:

```python
# apps/tasks/apps.py
class TasksConfig(AppConfig):
    name = "tasks"

    def ready(self):
        import tasks.signals  # noqa: F401
```

## Views and URL Routing

### CBVs vs FBVs

Use **class-based views** for standard CRUD that maps to Django generics (`ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView`). Use **function-based views** for one-off endpoints — HTMX partial responses, JSON reorder endpoints, toggle actions. Don't force everything into one style.

```python
# apps/plans/views.py — CBV for standard CRUD
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


@require_POST
def bucket_reorder(request, plan_id):
    ordered_ids = json.loads(request.body).get("bucket_ids", [])
    plan = Plan.objects.for_user(request.user).get(pk=plan_id)
    reorder_buckets(plan, ordered_ids)
    return JsonResponse({"status": "ok"})
```

### Keep Business Logic Out of Views

Views orchestrate — receive request, call domain logic, return response. If a view exceeds ~20 lines, logic is leaking in:

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
    task.mark_complete()
    return redirect("plans:plan-board", plan_id=task.bucket.plan_id)
```

### URL Namespacing

Every app gets its own `urls.py` with `app_name`:

```python
# apps/plans/urls.py
app_name = "plans"

urlpatterns = [
    path("", views.PlanListView.as_view(), name="plan-list"),
    path("create/", views.PlanCreateView.as_view(), name="plan-create"),
    path("<int:plan_id>/board/", views.plan_board, name="plan-board"),
    path("<int:plan_id>/buckets/reorder/", views.bucket_reorder, name="bucket-reorder"),
]
```

Always use `{% url %}` and `reverse()` — never hardcode paths.

### Permission Checks

Scope querysets to the current user. Return 404 (not 403) for unauthorized access to avoid leaking object existence:

```python
task = get_object_or_404(
    Task.objects.filter(bucket__plan__team__memberships__user=request.user),
    pk=task_id,
)
```

## Background Tasks (Django 6)

Use the built-in `django.tasks` framework. Task functions live in `tasks.py` per app. Import the `@task` decorator as `django_task` to avoid confusion with the `apps.tasks` app:

```python
# apps/tasks/tasks.py
from django.tasks import task as django_task

@django_task()
def send_assignment_notification(task_id: int, assignee_id: int) -> None:
    ...
```

| Environment | Backend | Behavior |
|---|---|---|
| Development | `ImmediateBackend` | Tasks run inline, blocking the request |
| Test | `DummyBackend` | Tasks captured but not executed — assert enqueuing |
| Production | `DatabaseBackend` | Stored in PostgreSQL, executed by `manage.py db_worker` |

Enqueue from signals, not views. Use `.using(queue_name=...)` in production to route work to specific queues:

```python
# apps/tasks/signals.py
@receiver(post_save, sender=Assignment)
def notify_assignee(sender, instance, created, **kwargs):
    if created:
        send_assignment_notification.using(queue_name="notifications").enqueue(
            instance.task_id, instance.user_id
        )
```

```python
# Production TASKS config with named queues
TASKS = {
    "default": {
        "BACKEND": "django_tasks.backends.database.DatabaseBackend",
        "QUEUES": ["default", "notifications", "attachments"],
    }
}
```

## Templates

Three-level template inheritance: base → section → page. Namespace templates under `<app_name>/` to avoid collisions.

Django 6 `{% partialdef %}` defines reusable fragments inline — no need for separate partial files:

```html
{% partialdef task_card %}
<div class="task-card" id="task-{{ task.pk }}">
    <h4>{{ task.title }}</h4>
    {% if task.is_overdue %}<span class="badge overdue">Overdue</span>{% endif %}
</div>
{% endpartialdef %}
```

Return just the partial from a view using the `#fragment_name` suffix:

```python
return render(request, "tasks/task_card.html#task_card", {"task": task})
```

Keep logic out of templates — use model properties (`task.is_overdue`) instead of computing in `{% if %}` chains.

## Query Optimization

- `select_related()` for FK/OneToOne (JOIN in one query)
- `prefetch_related()` for M2M/reverse FK (separate query)
- `Prefetch()` objects for filtered prefetches
- `update_fields` on `save()` for leaner UPDATEs
- Use `django-debug-toolbar` in development to catch N+1 queries

```python
# Board view — 4 queries instead of hundreds
plan = Plan.objects.prefetch_related(
    "buckets__tasks__assignees",
    "buckets__tasks__labels",
    "buckets__tasks__checklist_items",
).get(pk=plan_id)
```

Use `Prefetch()` when you need to filter or customize the prefetched queryset:

```python
from django.db.models import Prefetch

# "My Tasks" view — only incomplete tasks assigned to current user
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

## Testing

pytest-django with factory_boy. Configure in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--reuse-db --no-migrations -q --import-mode=importlib"

[tool.coverage.run]
source = ["apps/"]
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 85
```

No root-level `conftest.py`. Place shared fixtures in `apps/conftest.py` (project-wide) or `apps/<app>/tests/conftest.py` (app-specific) when needed.

Factories live in `apps/<app>/tests/factories.py`:

```python
class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    title = factory.Sequence(lambda n: f"Task {n}")
    bucket = factory.SubFactory(BucketFactory)
    created_by = factory.SubFactory(UserFactory)
    priority = Task.Priority.MEDIUM
```

### Model tests: only custom logic

Model tests should **only** cover custom methods, computed properties, and business logic you wrote. Do not test Django's built-in behavior — field declarations, `__str__`, basic CRUD, `auto_now`/`auto_now_add`, constraints enforced by migrations, or ORM defaults all work because Django works.

**Test** — custom methods (`mark_complete()`), properties (`is_overdue`), custom managers/querysets (`for_user()`, `overdue()`), and any non-trivial logic.

**Skip** — `__str__`, field existence, field types, `pk` identity, `USERNAME_FIELD`, `Meta.ordering`, basic save/retrieve, constraint enforcement.

```python
# GOOD — tests custom property logic with meaningful edge cases
class TestTask:
    def test_is_overdue_when_past_due_and_incomplete(self):
        task = TaskFactory(
            due_date=timezone.now().date() - timedelta(days=1),
            progress=Task.Progress.NOT_STARTED,
        )
        assert task.is_overdue is True

    def test_not_overdue_when_completed(self):
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

```python
# BAD — tests Django, not your code
class TestTask:
    def test_str(self):
        task = TaskFactory(title="Do stuff")
        assert str(task) == "Do stuff"

    def test_has_title_field(self):
        task = TaskFactory()
        assert hasattr(task, "title")

    def test_created_at_auto_set(self):
        task = TaskFactory()
        assert task.created_at is not None
```

Test background tasks with `DummyBackend`:

```python
def setup_method(self):
    default_task_backend.clear()

def test_assignment_enqueues_notification(self):
    Assignment.objects.create(task=task, user=user)
    results = default_task_backend.results
    assert len(results) == 1
```

## Code Quality

Ruff for linting and formatting, ty for type checking. Both configured in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py314"
line-length = 99

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "DJ", "S"]
ignore = ["S101"]

[tool.ruff.lint.isort]
known-first-party = ["apps"]

[tool.ty]
python-version = "3.14"
```

```bash
ruff check .           # lint
ruff check . --fix     # lint + autofix
ruff format .          # format
ty check               # type check
```

## Migrations

- Never mix schema and data changes in the same migration
- Rename auto-generated files descriptively after creation
- Always commit migrations — conflicting migrations come from not committing early
- Use `RunPython` in a separate migration for data backfills

## Reference Guides

These cover specialized topics in depth — read them when the relevant pattern comes up:

- **[Models and database](references/models-and-database.md)** — full model layer, constraints, indexes, composite PKs, migration hygiene
- **[REST API with DRF](references/rest-api.md)** — serializers, ViewSets, permissions, filtering, JWT auth, OpenAPI docs, CORS
- **[Testing](references/testing.md)** — factory patterns, model/view/API tests, background task testing, coverage
- **[Templates](references/templates.md)** — inheritance, namespacing, partials, CSP nonces, static files, forms
- **[HTMX](references/htmx.md)** — CSRF setup, returning partials, toggle/inline-edit/reorder/delete patterns
- **[Full-text search](references/search.md)** — Postgres FTS with GeneratedField (Tier 1) and django-pgtrigger (Tier 2)
- **[Deployment](references/deployment.md)** — Docker, Gunicorn, WhiteNoise, background workers, health checks, structured logging
- **[Migrating to Django 6](references/migrating-to-django6.md)** — step-by-step upgrade from 5.x: replacing django-csp, adopting django.tasks, template partials, removed features
