# Migrating from Django 5.x to Django 6

## Overview

Django 6 is the next major release after the 5.x LTS series. It requires Python 3.13+ and brings several features that replace third-party packages. This guide covers what to change, what to replace, and what to adopt.

## Prerequisites

- **Python 3.13+** — Django 6 drops support for Python 3.11 and 3.12.
- **PostgreSQL 16+** — older versions are no longer supported.
- Run through Django 5.2 first if you're on 5.0 or 5.1 — don't skip major versions.

## Step-by-Step Migration

### 1. Fix All Deprecation Warnings First

Before upgrading, run your test suite with deprecation warnings visible:

```bash
python -Wa manage.py test
```

Or with pytest:

```bash
pytest -W always::DeprecationWarning
```

Fix every warning. Django removes deprecated features in the next major version — what was a warning in 5.x becomes an error in 6.0.

### 2. Update Dependencies

Update `django` and check that all third-party packages support Django 6:

```bash
pip install --upgrade django>=6.0
```

Check compatibility for common packages:
- `django-debug-toolbar` — check for 6.x-compatible release
- `django-filter` — usually fast to update
- `djangorestframework` — check release notes
- `django-cors-headers` — check release notes
- `factory-boy` — usually compatible without changes
- `pytest-django` — check for 6.x support

### 3. Replace `django-csp` with Native CSP

Django 6 ships `ContentSecurityPolicyMiddleware` built-in. If you're using `django-csp`, replace it.

**Before (django-csp):**

```python
# settings.py
INSTALLED_APPS = [..., "csp", ...]
MIDDLEWARE = [..., "csp.middleware.CSPMiddleware", ...]

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'",)
```

**After (Django 6 native):**

```python
# config/settings/production.py
from django.utils.csp import CSP

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",  # add after SecurityMiddleware
    ...
]

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

Add the CSP context processor for nonce support in templates:

```python
TEMPLATES = [
    {
        "OPTIONS": {
            "context_processors": [
                ...,
                "django.template.context_processors.csp",
            ],
        },
    },
]
```

Templates use `{{ csp_nonce }}` instead of the old `{% csp_nonce %}` tag:

```html
<!-- Before (django-csp) -->
{% load csp %}
<script nonce="{% csp_nonce %}">...</script>

<!-- After (Django 6) -->
<script nonce="{{ csp_nonce }}">...</script>
```

**Rollout strategy:** Start with `SECURE_CSP_REPORT_ONLY` to find violations, then switch to `SECURE_CSP` for enforcement.

Then remove the dependency:

```bash
pip uninstall django-csp
```

### 4. Adopt the Background Tasks Framework

Django 6 introduces `django.tasks` — a built-in background task system. If you're using Celery or django-rq for simple async jobs, you can migrate lightweight tasks to the new framework.

**Before (Celery):**

```python
# tasks.py
from celery import shared_task

@shared_task
def send_notification_email(user_id, message):
    user = User.objects.get(pk=user_id)
    user.email_user(subject="Notification", message=message)

# calling
send_notification_email.delay(user.pk, "You were assigned a task")
```

**After (Django 6):**

```python
# tasks.py
from django.tasks import task

@task()
def send_notification_email(user_id: int, message: str) -> None:
    user = User.objects.get(pk=user_id)
    user.email_user(subject="Notification", message=message)

# calling
send_notification_email.enqueue(user.pk, "You were assigned a task")
```

Configure the `TASKS` setting per environment:

```python
# config/settings/base.py — development default
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.immediate.ImmediateBackend",
    }
}

# config/settings/test.py — capture without executing
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.dummy.DummyBackend",
    }
}

# config/settings/production.py — persistent with worker process
INSTALLED_APPS += ["django_tasks", "django_tasks.backends.database"]
TASKS = {
    "default": {
        "BACKEND": "django_tasks.backends.database.DatabaseBackend",
        "QUEUES": ["default", "notifications"],
    }
}
```

Production requires a worker process:

```bash
python manage.py db_worker
```

**When to keep Celery:** Keep Celery if you need periodic/cron scheduling (Celery Beat), complex task chains and chords, priority queues beyond what DatabaseBackend offers, or Redis/RabbitMQ broker features. Django's built-in tasks are best for simple fire-and-forget jobs like sending emails and processing uploads.

### 5. Adopt Template Partials

Django 6 introduces `{% partialdef %}` for defining reusable template fragments inline. This replaces the pattern of splitting every small HTMX snippet into a separate file.

**Before (separate file for every fragment):**

```
templates/tasks/
├── task_card.html
├── _task_card_fragment.html    # just for HTMX responses
├── task_detail.html
└── _checklist_item.html        # another fragment
```

```python
# views.py — returning a fragment
return render(request, "tasks/_task_card_fragment.html", {"task": task})
```

**After (inline partials):**

```html
{# templates/tasks/task_card.html #}
{% partialdef task_card %}
<div class="task-card" id="task-{{ task.pk }}">
    <h4>{{ task.title }}</h4>
    {% if task.is_overdue %}<span class="badge overdue">Overdue</span>{% endif %}
</div>
{% endpartialdef %}
```

```python
# views.py — returning just the partial
return render(request, "tasks/task_card.html#task_card", {"task": task})
```

The `#task_card` suffix tells Django to render only that partial, not the whole template. You can define multiple partials in one file. The full template still works as a normal template when rendered without the `#` suffix.

### 6. Use `AsyncPaginator` for Async Views

Django 6 provides `AsyncPaginator` and `AsyncPage` for async view support:

**Before:**

```python
# Blocking paginator in an async view — blocks the event loop
async def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    paginator = Paginator(notifications, 25)  # sync
    page = paginator.get_page(request.GET.get("page"))
    ...
```

**After:**

```python
from django.core.paginator import AsyncPaginator

async def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    paginator = AsyncPaginator(notifications, 25)
    page = await paginator.aget_page(request.GET.get("page"))
    ...
```

### 7. Review Removed Features

Features deprecated in Django 5.x are removed in 6.0. Common ones to watch for:

- **`unique_together`** — use `UniqueConstraint` in `Meta.constraints` instead
- **`index_together`** — use `Index` in `Meta.indexes` instead
- **`django.utils.encoding.force_text`** — use `force_str`
- **`django.conf.urls.url()`** — use `path()` or `re_path()`
- **`NullBooleanField`** — use `BooleanField(null=True)`
- **`default_app_config`** in `__init__.py` — Django auto-discovers `AppConfig` subclasses since 3.2
- **`django.utils.translation.ugettext`** — use `gettext`

Check the Django 6.0 release notes for the complete removal list.

### 8. Update `pyproject.toml` Tooling

Update your tooling targets:

```toml
[tool.ruff]
target-version = "py313"     # was py312 or py311

[tool.ty]
python-version = "3.13"

[project]
requires-python = ">=3.13"
```

## Migration Checklist

1. **Run tests with `-Wa`** to surface all deprecation warnings and fix them
2. **Upgrade Django** to 6.0+ and all third-party packages
3. **Run `manage.py check --deploy`** to catch any new system checks
4. **Replace `django-csp`** with native `SECURE_CSP` / `ContentSecurityPolicyMiddleware`
5. **Replace `unique_together` / `index_together`** with `UniqueConstraint` / `Index` if not already done
6. **Adopt `django.tasks`** for simple background jobs (keep Celery for complex workflows)
7. **Adopt `{% partialdef %}`** for HTMX fragments instead of separate template files
8. **Use `AsyncPaginator`** in async views
9. **Update `pyproject.toml`** target versions to Python 3.13
10. **Run the full test suite** and fix any breakage
11. **Test migrations** on a staging database with realistic data before deploying
