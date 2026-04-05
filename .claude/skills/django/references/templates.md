# Templates

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

## Template Namespacing

Always namespace templates under `<app_name>/` to avoid collisions between apps. Both `plans` and `tasks` could have a `detail.html` — without namespacing, one silently shadows the other:

```
# WRONG — collision risk
apps/plans/templates/board.html
apps/tasks/templates/detail.html

# RIGHT — namespaced
apps/plans/templates/plans/plan_board.html
apps/tasks/templates/tasks/task_detail.html
```

## Django 6 Template Partials

`{% partialdef %}` defines reusable template fragments inline, eliminating the need to split every small snippet into a separate file:

```html
{# templates/tasks/task_card.html #}

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

Return just the partial from a view using the `#fragment_name` suffix:

```python
def toggle_checklist_item(request, item_id):
    item = get_object_or_404(ChecklistItem, pk=item_id)
    item.is_completed = not item.is_completed
    item.save(update_fields=["is_completed", "updated_at"])
    task = item.task
    return render(request, "tasks/task_card.html#task_card", {"task": task})
```

You can define multiple partials in one file. The full template still renders normally without the `#` suffix.

## Keep Logic Out of Templates

Templates display data — they don't compute it. If `{% if %}` chains span 10+ lines, move the logic to the model, a template tag, or the view context:

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

## Content Security Policy (Django 6)

Django 6 ships native CSP support. Add `django.template.context_processors.csp` to context processors, then use nonces in templates:

```html
<link rel="stylesheet" href="{% static 'css/planly.css' %}" nonce="{{ csp_nonce }}">
<script src="{% static 'js/board.js' %}" nonce="{{ csp_nonce }}"></script>
<script nonce="{{ csp_nonce }}">
    PlanlyBoard.init("{{ plan.pk }}");
</script>
```

Configure CSP in production settings:

```python
# config/settings/production.py
from django.utils.csp import CSP

MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
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
```

Start in report-only mode (`SECURE_CSP_REPORT_ONLY`) to find violations before enforcing.

## Static Files

Project-wide assets in top-level `static/`. App-specific in `apps/<app>/static/<app>/`:

```python
# config/settings/base.py
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic target — gitignored
```

In production, run `collectstatic` in CI and serve with WhiteNoise.

## Forms

Centralize validation in forms, not views:

```python
# apps/tasks/forms.py
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "bucket", "priority",
                  "start_date", "due_date", "assignees", "labels"]
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
```
