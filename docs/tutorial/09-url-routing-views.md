# Chapter 9 — URL Routing & Views

## Goal

By the end of this chapter you'll have:

- A clean project-level `config/urls.py` that follows the same patterns mature production projects use (we crib from `cookiecutter-django`)
- App-level `urls.py` for plans, tasks, and notifications, each namespaced with `app_name`
- Class-based views for standard CRUD, function-based views for one-off actions
- Permission scoping driven by querysets — non-members get a clean `404`, never a `500`
- Minimal templates so every URL renders in the browser
- A focused set of view tests that exercise the *custom* logic and skip the framework's

After this chapter, the app actually works. You can log in, create a plan, add a task, and click "Mark complete." The styling is rough — that's Chapter 11's job — but the data flow is real.

---

## Why URLs Are Architecture, Not Plumbing

A URL conf is a contract between the front door and everything behind it. Three things you want it to do well:

1. **Make the public surface obvious.** Reading `config/urls.py` should tell you what the app *is*, in one screen.
2. **Keep app concerns inside apps.** The project file shouldn't know that plans have buckets — it should just `include("apps.plans.urls", namespace="plans")` and let the plans app define its own world.
3. **Compose with environments.** The dev server needs media files served, error-page previews, and the debug toolbar. Production needs an obscured admin path. The same `urls.py` should support both without becoming a tangle of `if`s.

We'll borrow heavily from `cookiecutter-django`'s URL conventions. Their template has been refined across thousands of projects — there's no reason to reinvent.

---

## Step 1: Make the Admin URL Configurable

Right now `config/urls.py` has `path("admin/", admin.site.urls)`. That's fine in dev. In production it's a problem: bots constantly probe `/admin/` for known Django installs, and a hard-to-guess path gives you one extra layer between the public internet and your admin login.

Add an `ADMIN_URL` setting in `config/settings/base.py`:

```python
# URL prefix for the Django admin. Defaults to "admin/" for local dev; in
# production set DJANGO_ADMIN_URL to a hard-to-guess path so the admin login
# page isn't sitting at a well-known URL for bots to hammer.
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "admin/")
```

Add it to `.env.example`:

```env
DJANGO_ADMIN_URL=admin/                          # production: set to a hard-to-guess path (must end with "/")
```

In Chapter 16 we'll add a production-settings check that fails fast if `DJANGO_ADMIN_URL` is left at the default. For now the env var is optional and falls back cleanly.

> **Why an env var, not a setting per environment?** Because the value is a *secret* — checking the production admin path into your repo defeats the purpose. Env vars also let you rotate it without a code change.

---

## Step 2: Project-Level `config/urls.py`

Here is the full project URL conf:

```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(settings.ADMIN_URL, admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("plans/", include("apps.plans.urls", namespace="plans")),
    path("tasks/", include("apps.tasks.urls", namespace="tasks")),
    path("notifications/", include("apps.notifications.urls", namespace="notifications")),
    # API URLs are wired up in Chapter 13.
    # path("api/", include("config.api_router")),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        from debug_toolbar.toolbar import debug_toolbar_urls

        urlpatterns = [*debug_toolbar_urls(), *urlpatterns]
```

Worth walking through, line by line, since several of these decisions are non-obvious.

### `TemplateView` for the home page

```python
path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
```

The earlier draft of this file had `RedirectView.as_view(pattern_name="plans:plan-list")` at `/`. That's fine *if every visitor is logged in*. But anonymous visitors hitting `/` would bounce through redirect → login redirect, which is two redirects to display anything useful. A static landing page is friendlier and gives you a place to put marketing copy later.

`TemplateView` keeps the route declarative — there's no view function to write, no test to maintain. The URL has a `name` so other templates can `{% url 'home' %}`.

### `settings.ADMIN_URL` instead of a literal `"admin/"`

```python
path(settings.ADMIN_URL, admin.site.urls),
```

Same payload as before — just driven by config. Local dev still gets `/admin/`; production sets `DJANGO_ADMIN_URL=ops/super-secret/` (or whatever you like) and bots scanning `/admin/` get a 404.

### Built-in auth URLs at `/accounts/`

```python
path("accounts/", include("django.contrib.auth.urls")),
```

Django ships with views for login, logout, password change, password reset, password reset confirm — eight views in total. They render templates from `registration/<viewname>.html` (under either project-level `templates/` or app-level template dirs). We already created `templates/registration/login.html`. The other templates can be added in Chapter 11 when we polish the UI.

> **Why `/accounts/`, not `/auth/` or `/login/`?** Because Django's `LOGIN_URL` setting and `login_required` decorator both default to `/accounts/login/`. Following the convention means less configuration.

### Media files in development

```python
*static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
```

In production, S3 (or whatever object storage you're using) serves uploaded files directly — Django never sees the request. In development we don't have S3, so Django itself needs to serve `MEDIA_URL`. The `static()` helper returns a list of URL patterns; we splat it (`*`) into `urlpatterns`. The helper is a no-op when `DEBUG=False`, so this is safe to leave in production code — it only does something in dev.

### Error-page previews

```python
if settings.DEBUG:
    urlpatterns += [
        path("400/", default_views.bad_request, ...),
        path("403/", default_views.permission_denied, ...),
        path("404/", default_views.page_not_found, ...),
        path("500/", default_views.server_error),
    ]
```

When you customize `404.html` or `500.html`, you can't easily preview them — Django only renders error templates when `DEBUG=False`, and even then only for actual errors. These dev-only routes render the same templates on demand, so you can iterate on them. They're gated on `DEBUG`, so they never appear in production.

### Debug toolbar URLs

```python
    if "debug_toolbar" in settings.INSTALLED_APPS:
        from debug_toolbar.toolbar import debug_toolbar_urls

        urlpatterns = [*debug_toolbar_urls(), *urlpatterns]
```

Two things going on here:

- **`if "debug_toolbar" in settings.INSTALLED_APPS:`** — only set up the toolbar URLs when the toolbar is actually installed. We turn it on in `config/settings/local.py` and leave it off in test/production. This guard means the URL conf works in every environment.
- **Local import** — yes, this violates our top-level-imports rule. The exception is the explicit one in our code-style notes: imports needed only to avoid breaking on a missing optional dependency. If the toolbar isn't installed, importing it at module top would crash every settings module, even tests.
- **`debug_toolbar_urls()`** — the new (DDT 4.4+) helper, replacing the legacy `path("__debug__/", include(debug_toolbar.urls))`. It returns a list of patterns and is a drop-in.

We prepend the toolbar URLs (`[*debug_toolbar_urls(), *urlpatterns]`) so they win over any catch-all routes.

### What's *not* here yet

- **API URLs** — commented out, wired up in Chapter 13. We leave the slot to make the future shape obvious to a reader.
- **Static files** — handled by `staticfiles` in dev (`runserver` serves them automatically) and WhiteNoise in production (Chapter 18).
- **Health check** — coming in Chapter 18.

---

## Step 3: Plans Views and URLs

The plans app gets the standard CRUD: list, detail, create, update, delete. All five map cleanly to Django's generic class-based views.

### Decision: CBV or FBV?

The trade-off:

- **CBV** — less code to write, but more layers of indirection. Maximum payoff when the view is *standard CRUD* matching a generic exactly.
- **FBV** — explicit and linear, but you write the boilerplate yourself. Maximum payoff when the view is doing something one-off (toggle a flag, return a JSON response, render an HTMX fragment).

**Rule we follow throughout the app: CBV for CRUD, FBV for one-off actions.** Don't mix them within a single view "for consistency." The right choice per view is what matters.

For the plans app, every view is CRUD — so all five are CBVs.

### `apps/plans/views.py`

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.tasks.models import Task

from .models import Bucket, Plan


class PlanListView(LoginRequiredMixin, ListView):
    model = Plan
    template_name = "plans/plan_list.html"
    context_object_name = "plans"

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user).with_task_counts()


class PlanDetailView(LoginRequiredMixin, DetailView):
    """Plan board — shows every bucket for the plan with its tasks."""

    model = Plan
    template_name = "plans/plan_detail.html"
    context_object_name = "plan"

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user).prefetch_related(
            Prefetch(
                "buckets",
                queryset=Bucket.objects.prefetch_related(
                    Prefetch("tasks", queryset=Task.objects.select_related("bucket")),
                ),
            ),
        )


class PlanCreateView(LoginRequiredMixin, CreateView):
    model = Plan
    fields = ["title", "description", "team", "visibility"]
    template_name = "plans/plan_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("plans:plan-detail", kwargs={"pk": self.object.pk})


class PlanUpdateView(LoginRequiredMixin, UpdateView):
    model = Plan
    fields = ["title", "description", "visibility"]
    template_name = "plans/plan_form.html"

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user)

    def get_success_url(self):
        return reverse_lazy("plans:plan-detail", kwargs={"pk": self.object.pk})


class PlanDeleteView(LoginRequiredMixin, DeleteView):
    model = Plan
    template_name = "plans/plan_confirm_delete.html"
    success_url = reverse_lazy("plans:plan-list")

    def get_queryset(self):
        return Plan.objects.for_user(self.request.user)
```

Three patterns worth calling out.

#### Permission scoping via `get_queryset()`

Every "object-needed" view (`Detail`, `Update`, `Delete`) overrides `get_queryset()` to scope to plans the user can see (`Plan.objects.for_user(self.request.user)`). Django's generic views use this queryset to find the object, so anything outside it returns a 404 — never a 403, never a leaked existence check.

This is the canonical Django security pattern. **Your views should never call `Plan.objects.get(pk=...)` directly** — go through a scoped queryset, always.

#### `PlanCreateView` doesn't override `get_queryset()`

Because there's no object to fetch — the form creates a new one. We do still need to set `created_by` and `owner` from the request user, which we do in `form_valid()`.

#### `Prefetch` in `PlanDetailView`

The plan-detail page renders every bucket and every task in those buckets. Without prefetching that's:

- 1 query for the plan
- 1 query for buckets
- N queries for tasks per bucket (one per bucket!)

With the `Prefetch` chain, it's 3 queries total regardless of how many buckets and tasks exist. We don't go further (e.g., prefetching `assignees` and `labels`) because the minimal template doesn't render them. Chapter 11 will add those when the template grows.

### `apps/plans/urls.py`

```python
from django.urls import path

from . import views

app_name = "plans"

urlpatterns = [
    path("", views.PlanListView.as_view(), name="plan-list"),
    path("create/", views.PlanCreateView.as_view(), name="plan-create"),
    path("<int:pk>/", views.PlanDetailView.as_view(), name="plan-detail"),
    path("<int:pk>/edit/", views.PlanUpdateView.as_view(), name="plan-update"),
    path("<int:pk>/delete/", views.PlanDeleteView.as_view(), name="plan-delete"),
]
```

Two conventions:

- **`app_name = "plans"`** — required for namespace lookups (`{% url 'plans:plan-list' %}`). Without it, you'd write `{% url 'plan-list' %}` and get cross-app collisions the moment two apps both have a `list` view.
- **Hyphens in URL names, not underscores** — `plan-list`, not `plan_list`. Convention varies but hyphens read better in templates and documentation. (Use whatever convention you adopt — but pick one and stick to it.)

---

## Step 4: Tasks Views and URLs

The tasks app gets the same CRUD patterns *plus* a one-off action: marking a task complete. That's where the FBV earns its keep.

### Permission scoping is one level deeper

A `Task` doesn't have a direct team relationship — it lives in a `Bucket`, which lives in a `Plan`, which has a `Team`. So the scoping query has to traverse three FKs:

```python
Task.objects.filter(bucket__plan__team__memberships__user=request.user)
```

We don't want to repeat that on every view, so we factor it into a mixin:

```python
class TaskScopedQuerysetMixin(LoginRequiredMixin):
    """Restrict tasks to those reachable through the user's team memberships."""

    def get_queryset(self):
        return Task.objects.filter(
            bucket__plan__team__memberships__user=self.request.user,
        ).distinct()
```

Three things worth noting:

- It inherits from `LoginRequiredMixin` so any view that uses this mixin gets login-required behavior automatically.
- `.distinct()` is needed because the JOIN through `memberships` can multiply rows if a user belongs to multiple memberships per team (which shouldn't happen, but the constraint is at the database level — defense in depth at the query level is cheap).
- This pattern — extract scoping into a mixin — generalizes well. You'll do the same for tasks-by-plan in Chapter 11 and tasks-by-assignee later on.

### `apps/tasks/views.py`

```python
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from apps.plans.models import Bucket

from .models import Task


class TaskScopedQuerysetMixin(LoginRequiredMixin):
    def get_queryset(self):
        return Task.objects.filter(
            bucket__plan__team__memberships__user=self.request.user,
        ).distinct()


class TaskDetailView(TaskScopedQuerysetMixin, DetailView):
    model = Task
    template_name = "tasks/task_detail.html"
    context_object_name = "task"


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    fields = ["title", "description", "priority", "due_date", "start_date"]
    template_name = "tasks/task_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.bucket = get_object_or_404(
            Bucket.objects.filter(plan__team__memberships__user=request.user),
            pk=kwargs["bucket_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.bucket = self.bucket
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.bucket.plan_id})


class TaskUpdateView(TaskScopedQuerysetMixin, UpdateView):
    model = Task
    fields = ["title", "description", "priority", "progress", "due_date", "start_date"]
    template_name = "tasks/task_form.html"

    def get_success_url(self):
        return reverse("tasks:task-detail", kwargs={"pk": self.object.pk})


class TaskDeleteView(TaskScopedQuerysetMixin, DeleteView):
    model = Task
    template_name = "tasks/task_confirm_delete.html"

    def get_success_url(self):
        return reverse("plans:plan-detail", kwargs={"pk": self.object.bucket.plan_id})


@login_required
@require_POST
def task_mark_complete(request, pk):
    task = get_object_or_404(
        Task.objects.filter(bucket__plan__team__memberships__user=request.user),
        pk=pk,
    )
    task.mark_complete()
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))
```

A few decisions worth dwelling on.

#### `TaskCreateView` resolves the bucket in `dispatch()`

The URL is `tasks/buckets/<int:bucket_pk>/create/`. The bucket is part of the URL because tasks always belong to a bucket — there's no "create a task in a vacuum" flow.

Resolving the bucket in `dispatch()` (rather than in `form_valid()` or `get_context_data()`) means we get the 404 *before* the form even renders, and the bucket is available to every other method on the view. We use it in `form_valid()` to set `bucket` and in `get_success_url()` to redirect back to the plan page.

#### `task_mark_complete` is a function-based view

This view doesn't render a form, doesn't have a generic equivalent, and only handles a single action. Trying to express it as a CBV would mean fighting the framework — `View`'s base class plus a `post()` method plus all the import boilerplate, just to get back to the same six lines.

The decorators stack matters:

```python
@login_required
@require_POST
def task_mark_complete(request, pk):
    ...
```

- `@login_required` — outermost, runs first. If the user isn't logged in, they're redirected to `/accounts/login/` *before* `@require_POST` even checks the method.
- `@require_POST` — runs after auth. Returns `405 Method Not Allowed` for `GET`s. (If you flipped the order, an anonymous `GET` would get `405` instead of a login redirect — wrong.)

#### Why call `task.mark_complete()` instead of writing the logic in the view?

Because that's where it belongs. The "fat models, thin views" rule from Chapter 6 isn't aesthetic — it has practical consequences:

- The same logic runs from the API in Chapter 13 (without copy-pasting).
- It runs from background tasks in Chapter 12 (without web request context).
- It can be unit-tested without a `Client` (the test for `mark_complete()` itself is in `test_models.py`, not `test_views.py`).

Views orchestrate. Models do the work.

### `apps/tasks/urls.py`

```python
from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("buckets/<int:bucket_pk>/create/", views.TaskCreateView.as_view(), name="task-create"),
    path("<int:pk>/", views.TaskDetailView.as_view(), name="task-detail"),
    path("<int:pk>/edit/", views.TaskUpdateView.as_view(), name="task-update"),
    path("<int:pk>/delete/", views.TaskDeleteView.as_view(), name="task-delete"),
    path("<int:pk>/complete/", views.task_mark_complete, name="task-complete"),
]
```

The `buckets/<int:bucket_pk>/create/` route is a little awkward, but it's honest: tasks need a bucket, and putting the bucket in the URL makes that explicit. The alternative (a query param like `?bucket=42`) hides the requirement and makes URL reversing weirder.

---

## Step 5: Notifications Views and URLs

The notifications app has only two interactions: read the list, mark stuff as read.

### `apps/notifications/views.py`

```python
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 25

    def get_queryset(self):
        return Notification.objects.for_user(self.request.user).select_related("actor")


@login_required
@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(
        Notification.objects.for_user(request.user),
        pk=pk,
    )
    notification.mark_read()
    return HttpResponseRedirect(reverse("notifications:notification-list"))


@login_required
@require_POST
def notification_mark_all_read(request):
    Notification.objects.for_user(request.user).mark_all_read()
    return HttpResponseRedirect(reverse("notifications:notification-list"))
```

Three things worth noting.

#### `paginate_by = 25`

Notifications are an unbounded list — a busy user might have thousands. `ListView` handles pagination for free if you set `paginate_by`. The template gets `page_obj` and `paginator` automatically.

#### `select_related("actor")`

Each notification renders the actor's name (`{{ n.actor }}`). Without `select_related`, that's `paginate_by + 1` queries (one for the page of notifications, one per notification for the actor). With it, it's still 2 queries.

#### Why two FBVs for marking read?

Because the *unit of work* is different:

- `notification_mark_read(pk)` — marks one notification, on a specific row.
- `notification_mark_all_read()` — sweeps every unread notification for this user.

The single-mark version takes a `pk` and uses `get_object_or_404` for scoping. The sweep doesn't take a pk and runs a single `UPDATE` (in the queryset method `mark_all_read()`). Both are POST-only because they mutate state.

> **Why a queryset method instead of a model method for the sweep?** Because the operation works across many rows. A model method runs on a single instance — calling `notification.mark_all_read()` on each row would be `N` queries instead of one. Bulk operations belong on the queryset.

### `apps/notifications/urls.py`

```python
from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="notification-list"),
    path("<int:pk>/read/", views.notification_mark_read, name="notification-mark-read"),
    path("read-all/", views.notification_mark_all_read, name="notification-mark-all-read"),
]
```

---

## Step 6: Minimal Templates

We need enough templates to make every URL render. Style is rough on purpose — Chapter 11 polishes everything with HTMX and a CSS framework.

The base template (`templates/base.html`) and the home page (`templates/pages/home.html`) live in the project-level `templates/` directory because they're cross-app. App-specific templates live under `apps/<app>/templates/<app>/` so they're discovered by Django's app loader.

The full set, all of which extend `base.html`:

- `apps/plans/templates/plans/plan_list.html`
- `apps/plans/templates/plans/plan_detail.html`
- `apps/plans/templates/plans/plan_form.html` (used by both Create and Update — the `{% if object %}` toggle handles labels)
- `apps/plans/templates/plans/plan_confirm_delete.html`
- `apps/tasks/templates/tasks/task_detail.html`
- `apps/tasks/templates/tasks/task_form.html`
- `apps/tasks/templates/tasks/task_confirm_delete.html`
- `apps/notifications/templates/notifications/notification_list.html`

A few patterns repeat across all of them:

- `{% url 'plans:plan-detail' plan.pk %}` — namespaced URL lookups, never hardcoded paths
- `{% csrf_token %}` inside every `<form method="post">` — Django enforces this on all unsafe methods
- `{{ form.as_p }}` — quick-and-dirty form rendering. We'll replace this with hand-rolled markup in Chapter 11

The `pages/home.html` is a real (if stubby) landing page — it shows different content for authenticated vs anonymous users:

```html
{% extends "base.html" %}

{% block title %}Planly{% endblock %}

{% block content %}
<h1>Planly</h1>
<p>A simple, fast task planner for small teams.</p>

{% if user.is_authenticated %}
  <p><a href="{% url 'plans:plan-list' %}">Go to your plans →</a></p>
{% else %}
  <p><a href="{% url 'login' %}">Log in</a> to get started.</p>
{% endif %}
{% endblock %}
```

---

## Step 7: View Tests

Unlike model tests, view tests are about *integration*: the URL routes correctly, the view applies the right scoping, the form sets the right fields, the redirect points to the right URL. Skip framework behavior — pagination working, `LoginRequiredMixin` redirecting, `CreateView` calling `save()`. Test the parts you actually wrote.

Three rules we follow:

1. **Hit the real URL** via `reverse()` and `client.get/post`. Don't import the view function and call it directly — that bypasses the URL conf, middleware, and decorators.
2. **Use `client.force_login(user)`** instead of `client.login(...)` with credentials. We're not testing the login flow here; we just need an authenticated client.
3. **Test what you wrote.** Permission scoping (does a non-member get a 404?), `created_by` auto-set, redirect targets, `mark_complete` actually marking complete. Don't test that `LoginRequiredMixin` redirects anonymous users — that's Django.

Below is the plans test file in full. The patterns repeat in `apps/tasks/tests/test_views.py` and `apps/notifications/tests/test_views.py`.

```python
import pytest
from django.urls import reverse

from apps.accounts.tests.factories import MembershipFactory, UserFactory
from apps.plans.models import Plan
from apps.plans.tests.factories import PlanFactory


@pytest.fixture
def member_and_plan(db):
    user = UserFactory()
    plan = PlanFactory()
    MembershipFactory(team=plan.team, user=user)
    return user, plan


@pytest.mark.django_db
class TestPlanListView:
    def test_only_lists_plans_user_can_see(self, client):
        user = UserFactory()
        my_plan = PlanFactory()
        MembershipFactory(team=my_plan.team, user=user)
        PlanFactory()  # someone else's plan

        client.force_login(user)
        response = client.get(reverse("plans:plan-list"))

        assert list(response.context["plans"]) == [my_plan]

    def test_redirects_anonymous_to_login(self, client):
        response = client.get(reverse("plans:plan-list"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url
```

Two things worth pointing at.

#### `member_and_plan` fixture

The membership graph is non-trivial: a user, a team, a plan, and a membership linking them. The fixture builds the whole shape in three lines and is reused across every test that needs it. Define fixtures in test files first; promote them up to `apps/conftest.py` only if multiple files need them.

#### Asserting on `response.context`, not the rendered HTML

`response.context["plans"]` is the queryset `ListView` passed to the template. Asserting on it is faster, more explicit, and decoupled from the template's HTML. We *do* assert on `response.url` for redirect targets — that's the contract `client.post` exposes — but we don't grep the body for strings. (We're trusting the template to render what we give it; if the template is wrong, that's a different test.)

### Skipping framework behavior

Things we don't test, even though they pass:

- `paginate_by = 25` actually paginates. (Django's tests cover that.)
- `LoginRequiredMixin` redirects. (Django's tests cover that.)
- `CreateView.form_valid` saves the model. (Django's tests cover that.)
- The DELETE confirmation template renders. (Visual; not test-worthy.)

Things we do test:

- Queryset scoping — a non-member gets `404`, the queryset filter is doing its job.
- Auto-set fields — `created_by` and `owner` are pulled from `request.user`.
- Redirect targets — `PlanCreateView` redirects to the new plan's detail page, not the list.
- `task_mark_complete` flips `progress` to `COMPLETED` and stamps `completed_at`.
- `notification_mark_all_read` only touches the requesting user's *unread* notifications.

> **Why so picky?** Because every test you write is code you have to maintain. A test that just exercises Django's generic-view plumbing has high carrying cost and zero signal — when it fails, it'll fail because Django changed, and you'll have to fix it without learning anything.

---

## Verify

```bash
docker compose exec web uv run python manage.py check
docker compose exec web uv run pytest
```

Both should pass clean. Then poke the app in a browser:

```bash
# Visit http://localhost:8000/         — the home page
# Visit http://localhost:8000/admin/   — the admin (will redirect to login)
# Visit http://localhost:8000/404/     — preview the 404 template
```

If the admin login form looks weird, that's because we haven't styled it yet — Django's default UserAdmin templates assume a `username` field, and we have `employee_id`. Chapter 11 picks that up.

---

## What we don't test (yet)

- **Templates** — they render or they don't, and the integration tests will catch obvious breakage. Visual testing happens in the browser.
- **Form validation** — Chapter 10 introduces `ModelForm` subclasses with custom validators, and that's where validation tests belong.
- **HTMX flows** — the current templates submit standard HTML forms. HTMX comes in Chapter 11.
- **Query counts** — Chapter 17 (Performance) adds `assertNumQueries` tests against the prefetch chains we set up here.

The chapter-9 surface is "the URL conf works, the views scope correctly, the redirects go where they should." Anything else can wait for the chapter that's actually about it.

---

## Recap

You added:

- A configurable `ADMIN_URL` setting and a clean project-level `config/urls.py` modeled on `cookiecutter-django`
- App-level `urls.py` for plans, tasks, and notifications, all namespaced
- 5 plans CBVs, 4 tasks CBVs + 1 mark-complete FBV, 1 notifications CBV + 2 sweep FBVs
- A `TaskScopedQuerysetMixin` that captures the standard "tasks visible through team membership" pattern
- Minimal templates that make every URL render
- 19 view tests covering permission scoping, auto-set fields, and the redirect targets we wrote

The data layer is now reachable from the browser. Chapter 10 adds form classes and validation; Chapter 11 makes the UI actually pleasant.

---

## Suggested commit

```
add Chapter 9 — URL routing & views

- Refactor config/urls.py to follow cookiecutter-django patterns:
  configurable ADMIN_URL, TemplateView home page, dev-only error
  page previews and debug-toolbar URLs, media files in DEBUG only.
- Add app-level urls.py + views for plans, tasks, notifications.
- CBVs for CRUD; FBVs for task_mark_complete, notification mark-read,
  and notification mark-all-read. Permission scoping via querysets
  (.for_user / .filter(bucket__plan__team__memberships__user=...)).
- Add TaskScopedQuerysetMixin for repeated tasks-by-team-membership.
- 19 view tests covering scoping, auto-set fields, and redirect targets.
- Override pytest --ds in addopts so config.settings.test wins over
  the DJANGO_SETTINGS_MODULE inherited from the docker compose env.
```
