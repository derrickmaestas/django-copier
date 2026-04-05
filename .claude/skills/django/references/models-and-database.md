# Models and Database

## Complete Model Layer

### `core` — Abstract Bases

```python
# apps/core/models.py
from django.db import models


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


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
```

### `accounts` — Custom User and Teams

Always define a custom user model before the first migration, even if identical to `AbstractUser`:

```python
# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import UserManager
from core.models import TimeStampedModel


class User(AbstractUser):
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    job_title = models.CharField(max_length=100, blank=True)

    objects = UserManager()

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.display_name or self.username


class Team(TimeStampedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_teams")

    class Meta:
        ordering = ["name"]


class Membership(TimeStampedModel):
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
```

## `null` and `blank` — Decision Matrix

The core rule: **never use `null=True` on `CharField` or `TextField`**. With `null=True`, you get two "empty" values (`NULL` and `""`), and every filter must account for both.

| Field type | "Optional" means | Use |
|---|---|---|
| `CharField`, `TextField` | Empty string is fine | `blank=True` only |
| `DateField`, `DateTimeField` | No value yet | `null=True, blank=True` |
| `IntegerField`, `DecimalField` | No value yet | `null=True, blank=True` |
| `BooleanField` | Always True/False | `default=` instead |
| `ForeignKey` (optional) | Relationship absent | `null=True, blank=True` |
| `ForeignKey` (required) | Must always exist | Neither |
| `ManyToManyField` | Zero selections ok | `blank=True` only — never `null` |
| `FileField`, `ImageField` | Upload optional | `blank=True` only |
| `JSONField` | No data | `default=dict, blank=True` (preferred) or `null=True, blank=True` |

### `null=True` without `blank=True`

Used when a field is nullable in the database but not user-facing. Example: `created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)` — set in the view, never in a form. The absence of `blank=True` means a form would require it, acting as a safety net.

### `db_default` vs `default` (Django 5.2+)

`db_default` sets the default at the database level — it applies even when rows are inserted via raw SQL, data migrations, or other services bypassing the ORM. Use `db_default` for values the database can compute (constants, `Now()`). Use Python `default` for values that require Python logic (callables like `uuid.uuid4`, `timezone.now`):

```python
# Database can handle this — use db_default
is_read = models.BooleanField(db_default=False)

# Needs Python callable — use default
created_at = models.DateTimeField(default=timezone.now)
```

## Indexes

Use `Meta.indexes` with explicit names. Prefer partial and composite indexes over blanket `db_index=True`:

```python
class Task(TimeStampedModel):
    class Meta:
        indexes = [
            # Board view: fetch tasks in a bucket, sorted by priority
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

Composite index leftmost column matters: `["bucket", "priority"]` supports queries on `bucket` alone or `bucket` + `priority`, but not `priority` alone.

## Constraints

### UniqueConstraint (replaces `unique_together`)

```python
models.UniqueConstraint(fields=["plan", "name"], name="unique_label_per_plan")
```

### Deferrable Constraints for Reordering

When drag-and-dropping, intermediate states violate immediate uniqueness. `DEFERRED` checks at commit time:

```python
models.UniqueConstraint(
    fields=["plan", "position"],
    name="unique_bucket_position",
    deferrable=models.Deferrable.DEFERRED,
)
```

```python
from django.db import transaction

def reorder_buckets(plan, ordered_bucket_ids):
    with transaction.atomic():
        for position, bucket_id in enumerate(ordered_bucket_ids):
            Bucket.objects.filter(pk=bucket_id, plan=plan).update(position=position)
```

### CheckConstraint

```python
models.CheckConstraint(
    condition=models.Q(priority__in=[1, 3, 5, 9]),
    name="valid_task_priority",
),
models.CheckConstraint(
    condition=(
        models.Q(start_date__isnull=True)
        | models.Q(due_date__isnull=True)
        | models.Q(start_date__lte=models.F("due_date"))
    ),
    name="start_before_due",
),
```

## `on_delete` Strategies

| Strategy | When | Example |
|---|---|---|
| `CASCADE` | Child meaningless without parent | `Bucket.plan`, `Task.bucket`, `Comment.task` |
| `SET_NULL` | Child survives (requires `null=True`) | `Task.created_by`, `Comment.author` |
| `PROTECT` | Prevent destructive deletion | `Team.owner` |

## `related_name` — Always Set Explicitly

Especially when a model has multiple FKs to the same target:

```python
assignees = models.ManyToManyField(User, related_name="assigned_tasks")
created_by = models.ForeignKey(User, related_name="created_tasks")
```

Use `related_name="+"` when the reverse relation isn't needed.

## Custom QuerySets

```python
# apps/tasks/managers.py
class TaskQuerySet(models.QuerySet):
    def for_plan(self, plan):
        return self.filter(bucket__plan=plan)

    def for_user(self, user):
        return self.filter(assignments__user=user)

    def overdue(self):
        return self.filter(due_date__lt=timezone.now().date(), progress__lt=100)

    def due_today(self):
        return self.filter(due_date=timezone.now().date(), progress__lt=100)

    def by_priority(self):
        return self.order_by("priority", "due_date")

    def with_counts(self):
        return self.annotate(
            checklist_total=models.Count("checklist_items"),
            checklist_done=models.Count(
                "checklist_items",
                filter=models.Q(checklist_items__is_completed=True),
            ),
        )
```

Wire up: `objects = TaskQuerySet.as_manager()` on the model.

## Composite Primary Keys (Django 5.2+)

For junction tables where the combination of two FKs is the natural key:

```python
class Assignment(TimeStampedModel):
    pk = models.CompositePrimaryKey("task", "user")
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
```

Caveat: doesn't work with Django admin or some third-party packages. For broad compatibility, prefer `BigAutoField` PK with a `UniqueConstraint` instead.

## Migration Hygiene

- **Never mix schema and data changes** — schema migrations acquire locks; data migrations can be slow. Combining extends lock duration.
- **Rename migrations descriptively** after `makemigrations` — `0003_add_recurrence_rule_to_task.py` not `0003_auto_20260318_1422.py`.
- **Always commit migrations** — conflicting migrations come from not committing early.
- **Squash when they pile up** — `manage.py squashmigrations tasks 0001 0010`.
- **Test on realistic data** — a migration that works on empty tables can fail on millions of rows.
