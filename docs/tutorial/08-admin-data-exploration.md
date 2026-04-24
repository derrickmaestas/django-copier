# Chapter 8 — Admin & Data Exploration

## Goal

By the end of this chapter you'll have:
- Every model registered in the Django admin with sensible list views, filters, and search
- Inlines that let you edit related objects from a parent (buckets in a plan, checklist items in a task)
- A working `shell_plus` session for interactive data exploration
- Enough real data to spot-check that all the relationships from the previous chapters actually work

This is a short chapter, but it's the first time we're interacting with the app as users rather than as developers. Getting the admin right pays off for the entire life of the project — it's free internal tooling.

---

## Why the Admin Matters

The Django admin is often dismissed as "just for superusers." That undersells it:

- **Bug triage** — find the exact row that caused a report, see its related objects, follow FKs through the UI
- **Support** — reset a password, flip a flag, re-assign a task without writing a management command
- **Data QA** — spot-check that imports, migrations, and background tasks produced sensible data
- **First real validation** — before any views or forms exist, the admin is where you discover that your M2M through model won't save or your ordering is wrong

The rule of thumb: if a model is worth having in the database, it's worth being in the admin. Registration is three lines — the cost is zero.

---

## Step 1: Custom User Admin

The custom `User` model (employee ID as PK, no `username` field) needs a custom admin. Django's built-in `UserAdmin` assumes a `username` field and will crash if you just do `admin.site.register(User, UserAdmin)`.

Create `apps/accounts/admin.py`:

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.notifications.models import NotificationPreference

from .models import Discipline, Membership, Team, User


class NotificationPreferenceInline(admin.StackedInline):
    model = NotificationPreference
    can_delete = False
    extra = 0
    verbose_name_plural = "Notification preferences"


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["employee_id"]
    list_display = [
        "employee_id", "email", "display_name",
        "discipline", "is_manager", "is_staff",
    ]
    list_filter = ["is_staff", "is_superuser", "is_active", "is_manager", "discipline"]
    search_fields = ["employee_id", "email", "display_name"]
    autocomplete_fields = ["discipline"]
    inlines = [NotificationPreferenceInline]

    fieldsets = (
        (None, {"fields": ("employee_id", "password")}),
        ("Profile", {"fields": (
            "email", "display_name", "division",
            "organization", "discipline", "is_manager",
        )}),
        ("Permissions", {"fields": (
            "is_active", "is_staff", "is_superuser",
            "groups", "user_permissions",
        )}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("employee_id", "email", "password1", "password2"),
        }),
    )
```

### `@admin.register` vs `admin.site.register`

These are equivalent:

```python
# Decorator form
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    ...

# Imperative form
class TeamAdmin(admin.ModelAdmin):
    ...
admin.site.register(Team, TeamAdmin)
```

Prefer the decorator — the model and its admin class stay next to each other, and you don't have a dangling registration call at the bottom of the file.

### Why inherit from `BaseUserAdmin`?

`BaseUserAdmin` brings everything Django's built-in admin does for users: the password-change UI, the "add user" two-form flow (set a minimal user, then fill in the rest), and the permissions section. Inheriting lets us keep all of that and just override what's different.

The two must-override attributes are:

- **`fieldsets`** — controls the "change user" view. We replaced `first_name`/`last_name` with our profile fields.
- **`add_fieldsets`** — controls the "add user" view. We swapped `username` for `employee_id`.

Without `add_fieldsets`, clicking "Add user" would crash trying to render a `username` field that no longer exists.

### `autocomplete_fields` on FKs

```python
autocomplete_fields = ["discipline"]
```

By default, a FK in the admin renders as a full `<select>` with every row in the target table. That's fine for four disciplines; it's a disaster for 10,000 users. `autocomplete_fields` turns the field into a search box.

The target admin (`DisciplineAdmin`) needs `search_fields` configured, otherwise the autocomplete JSON endpoint has nothing to search. That's why every admin in this file has `search_fields`.

---

## Step 2: Inlines

Inlines let you edit child objects on the parent's page. Plans show their buckets, tasks show their checklist items, comments, assignments, and attachments, users show their notification preferences, teams show their memberships.

### `TabularInline` vs `StackedInline`

| Class | Layout | When to use |
|---|---|---|
| `TabularInline` | One row per object, fields as columns | Many short objects with a few fields (buckets, assignments) |
| `StackedInline` | One block per object, fields laid out vertically | Few objects with many fields, or a singleton (`NotificationPreference` 1:1) |

Rule of thumb: if the inline has three or more text fields, `StackedInline` reads better. Otherwise `TabularInline` is denser.

### Plans admin with BucketInline

Create `apps/plans/admin.py`:

```python
from django.contrib import admin

from .models import Bucket, Plan


class BucketInline(admin.TabularInline):
    model = Bucket
    extra = 0
    fields = ["position", "title"]
    ordering = ["position"]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["title", "team", "owner", "visibility", "created_at"]
    list_filter = ["visibility", "team"]
    search_fields = ["title", "description"]
    autocomplete_fields = ["team", "owner", "created_by"]
    inlines = [BucketInline]


@admin.register(Bucket)
class BucketAdmin(admin.ModelAdmin):
    list_display = ["title", "plan", "position"]
    list_filter = ["plan"]
    search_fields = ["title", "plan__title"]
    autocomplete_fields = ["plan"]
```

### Why `extra = 0`?

`extra` controls how many blank inline rows are rendered by default. Django defaults to `3`. For most cases that's annoying — three empty rows of buckets or comments on every edit page, and you have to delete them if you don't fill them in. Setting `extra = 0` means the inline only shows existing rows plus an "add another" button.

### Why we still register `BucketAdmin` even though it's inline on Plan

You can edit a bucket inside its plan, but you might still want a top-level view of all buckets for search, or for bulk operations. Every model gets its own admin registration; inlines are a convenience, not a replacement.

### Tasks admin with four inlines

Create `apps/tasks/admin.py`:

```python
from django.contrib import admin

from apps.attachments.models import Attachment

from .models import Assignment, ChecklistItem, Comment, Label, Task


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    autocomplete_fields = ["user"]


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0
    fields = ["position", "title", "is_completed"]
    ordering = ["position"]


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ["created_by", "body", "created_at"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["created_by"]


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ["filename", "uploaded_by", "size_bytes", "content_type", "created_at"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["uploaded_by"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "bucket", "priority", "progress", "due_date", "created_at"]
    list_filter = ["priority", "progress", "bucket__plan"]
    search_fields = ["title", "description"]
    autocomplete_fields = ["bucket", "created_by", "labels"]
    date_hierarchy = "due_date"
    inlines = [AssignmentInline, ChecklistItemInline, CommentInline, AttachmentInline]
```

Four inlines on one page isn't unusual for a central model like `Task`. The attachment inline lives in a different app (`apps.attachments`), but that's fine — inlines are defined where they're used, not where the model lives.

### `date_hierarchy`

```python
date_hierarchy = "due_date"
```

Adds a year/month/day drill-down bar at the top of the changelist. For any time-series data (tasks by due date, comments by created date, notifications by read date), this is a much faster way to filter than a list of filters.

### `list_filter` across relations

```python
list_filter = ["priority", "progress", "bucket__plan"]
```

List filters work through double-underscore traversal. `bucket__plan` lets you filter tasks by which plan they belong to, even though `plan` isn't a direct field on `Task`. Same syntax as in querysets.

---

## Step 3: The Other Admins

The remaining admin files are shorter — attachments, notifications, comments, labels, assignments, checklist items all get registered with `list_display`, `search_fields`, and `autocomplete_fields` so they can be edited top-level or serve autocompletes elsewhere.

Create `apps/attachments/admin.py`:

```python
from django.contrib import admin

from .models import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ["filename", "task", "uploaded_by", "size_mb", "created_at"]
    search_fields = ["filename", "task__title"]
    autocomplete_fields = ["task", "uploaded_by"]
    readonly_fields = ["size_bytes", "size_mb", "content_type"]

    @admin.display(description="Size (MB)")
    def size_mb(self, obj):
        return obj.size_mb
```

### `@admin.display` for computed columns

```python
@admin.display(description="Size (MB)")
def size_mb(self, obj):
    return obj.size_mb
```

`list_display` can include either field names or method names. Methods on the `ModelAdmin` take the object and return a value. The `@admin.display` decorator sets the column header and optionally sort behavior. We reference `obj.size_mb` — the model's property — so the computation lives on the model, not the admin.

Create `apps/notifications/admin.py`:

```python
from django.contrib import admin

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "actor", "verb", "target", "read_at", "created_at"]
    list_filter = ["verb", "read_at"]
    search_fields = ["recipient__email", "recipient__employee_id", "description"]
    autocomplete_fields = ["recipient", "actor"]
    readonly_fields = ["target_content_type", "target_object_id", "target"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "email_on_assignment",
        "email_on_comment",
        "email_on_due_soon",
        "daily_digest",
    ]
    search_fields = ["user__email", "user__employee_id"]
    autocomplete_fields = ["user"]
```

### Why `readonly_fields` on the GenericForeignKey triple?

```python
readonly_fields = ["target_content_type", "target_object_id", "target"]
```

Django's admin can't render a usable editor for a `GenericForeignKey` — the set of possible targets is every model in the system. Letting users set `content_type` + `object_id` by hand is an error-prone way to forge bad references. Notifications are created by application code (signals, management commands), so the admin just displays the target read-only.

---

## Step 4: Create a Superuser and Log In

Start the stack and create a user to log in as:

```bash
docker compose up -d
docker compose exec web uv run python manage.py migrate
docker compose exec web uv run python manage.py createsuperuser
```

`createsuperuser` uses `USERNAME_FIELD` and `REQUIRED_FIELDS` from the `User` model — it'll prompt for `employee_id`, `email`, and a password. Pick an employee_id like `1` for your dev admin.

Visit `http://localhost:8000/admin/`, log in, and click through:

- **Users** — profile fields show, notification preferences inline at the bottom
- **Teams** — member inline with role dropdowns
- **Plans** — buckets inline, ordered by position
- **Tasks** — four inlines stacked (assignments, checklist items, comments, attachments)
- **Notifications** — target shown read-only

Add a team with a few members, then a plan, then a bucket, then a task. Every relationship we spent the last three chapters declaring is now clickable.

---

## Step 5: Interactive Exploration with `shell_plus`

`django-extensions` ships `shell_plus`, which auto-imports every model before dropping you into a shell. It's already installed (in `local.py` dev dependencies).

```bash
docker compose exec web uv run python manage.py shell_plus
```

You'll see a message like:

```
# Shell Plus Model Imports
from apps.accounts.models import Discipline, Membership, Team, User
from apps.attachments.models import Attachment
from apps.notifications.models import Notification, NotificationPreference
from apps.plans.models import Bucket, Plan
from apps.tasks.models import Assignment, ChecklistItem, Comment, Label, Task
# ...
```

Every model is ready to use. Poke at the data you just created through the admin:

```python
>>> Plan.objects.for_user(User.objects.get(employee_id=1))
<PlanQuerySet [<Plan: My First Plan>]>

>>> plan = _[0]
>>> plan.buckets.all()
<QuerySet [<Bucket: To Do>, <Bucket: Doing>, <Bucket: Done>]>

>>> plan.buckets.first().tasks.count()
2

>>> Task.objects.overdue()
<TaskQuerySet []>

>>> Plan.objects.with_task_counts().values("title", "task_count", "completed_task_count")
<QuerySet [{'title': 'My First Plan', 'task_count': 2, 'completed_task_count': 0}]>
```

If any of these error out, you've found a bug in the model layer that no test covered. Fix it before moving on to views — debugging querysets in the shell is ten times faster than debugging them through a view.

### Useful `shell_plus` flags

```bash
shell_plus --print-sql      # show the SQL for every queryset
shell_plus --ipython        # use IPython (nicer REPL)
shell_plus --notebook       # open a Jupyter notebook
```

`--print-sql` is the quickest way to verify query optimization. If you're worried about N+1, run the code in `shell_plus --print-sql` and count the queries.

---

## Step 6: Run the Full Suite

Nothing changed in the data layer, but re-run the tests to confirm:

```bash
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web uv run pytest
```

All tests should still pass. Admin changes don't need tests — the admin is trusted framework code, and we're just configuring it declaratively.

---

## Why We Don't Test the Admin

Some teams write integration tests against admin views. For a standard `ModelAdmin`, this is wasted effort:

- `list_display` and `list_filter` either render or they don't — broken config raises on startup
- `autocomplete_fields` requires `search_fields` on the target — broken config raises on first search
- Inlines either save or don't — broken config raises on first save

All of these are surfaced by `manage.py check` or the first time you click through the admin. A dedicated test would just re-verify framework behavior.

If you ever add *custom admin views* (e.g., a bulk-assign action with a confirmation screen), test that — it's your code, not the framework's.

---

## Checkpoint

Before moving on, verify:

- [ ] `docker compose up` starts the stack and the admin loads at `http://localhost:8000/admin/`
- [ ] You can log in with the superuser you just created
- [ ] Every model shows in the admin index page
- [ ] The User change view shows the custom profile fields and notification preferences inline
- [ ] The Task change view shows all four inlines (assignments, checklist items, comments, attachments)
- [ ] `shell_plus` imports every model and `Plan.objects.for_user(user)` returns something
- [ ] `uv run pytest` still passes all tests

**Next:** [Chapter 9 — URL Routing & Views](09-url-routing-views.md)
