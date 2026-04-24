# Chapter 6 — Plans & Tasks: The Core Domain

## Goal

By the end of this chapter you'll have:
- `Plan` and `Bucket` models for organizing work into boards and columns
- `Task` with priority/progress enums, fat model methods (`is_overdue`, `mark_complete()`)
- `Assignment`, `ChecklistItem`, `Label`, and `Comment` models
- Custom QuerySets for both `Plan` and `Task` with scoping and annotation methods
- Factories and tests for everything above

This is the largest chapter so far — seven models across two apps. The patterns repeat, so the first few models get detailed explanations while the later ones move faster.

---

## The Data Model at a Glance

Here's how everything connects:

```
Team (accounts)
  └── Plan
        ├── Bucket (ordered)
        │     └── Task
        │           ├── Assignment → User (M2M through)
        │           ├── ChecklistItem (ordered)
        │           ├── Comment
        │           └── Label ←── (M2M, labels scoped to Plan)
        └── Label
```

A **Team** owns **Plans**. Each plan contains **Buckets** (columns like "To Do", "In Progress", "Done"). Buckets contain **Tasks**. Tasks can have **Assignments** (users assigned to work on them), **ChecklistItems** (sub-tasks), **Comments**, and **Labels** (colored tags shared across a plan).

---

## Plans App

### Step 1: Plan QuerySet

Before writing models, we write the queryset. The queryset defines how we'll query plans — scoped to the current user's team memberships, with optional task count annotations.

Why a separate `querysets.py`? Querysets contain chainable query logic (filtering, annotating, searching). Managers contain object creation logic (`create_user`, `create_superuser`). Most apps only need a queryset; managers are rare. Keeping them in separate files makes the distinction clear and keeps `models.py` focused on field definitions and business logic.

Create `apps/plans/querysets.py`:

```python
from django.db import models


class PlanQuerySet(models.QuerySet):
    """Custom queryset for Plan with team-scoped access and annotation helpers."""

    def for_user(self, user):
        """Return plans visible to this user through team membership."""
        return self.filter(team__memberships__user=user).distinct()

    def with_task_counts(self):
        """Annotate each plan with total and completed task counts."""
        return self.annotate(
            task_count=models.Count(
                "buckets__tasks",
                distinct=True,
            ),
            completed_task_count=models.Count(
                "buckets__tasks",
                filter=models.Q(buckets__tasks__progress=100),
                distinct=True,
            ),
        )
```

**`for_user()`** — the primary access control method. Instead of checking permissions in every view, you call `Plan.objects.for_user(request.user)` and get back only plans the user can see. The filter traverses three relations: Plan → Team → Membership → User.

**`.distinct()`** — prevents duplicates. A user might be in the same team multiple times if the query joins through multiple paths (though our data model doesn't allow that, it's defensive practice for JOINs across M2M-like relations).

**`with_task_counts()`** — annotates each plan with how many tasks it has and how many are completed. The `"buckets__tasks"` lookup spans two relations (Plan → Bucket → Task). `distinct=True` is critical here because the JOIN across multiple buckets would otherwise count the same task multiple times.

**`filter=models.Q(buckets__tasks__progress=100)`** — conditional aggregation. This counts only tasks where progress equals 100 (completed). Django translates this to a SQL `FILTER (WHERE ...)` clause, which is more efficient than a subquery.

### Step 2: Plan and Bucket Models

Create `apps/plans/models.py`:

```python
from django.conf import settings
from django.db import models

from apps.core.models import OrderedModel, TimeStampedModel

from .querysets import PlanQuerySet


class Plan(TimeStampedModel):
    """A plan (board) that organizes tasks into buckets for a team."""

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
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_plans",
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

    objects = PlanQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "-created_at"], name="idx_plan_team_created"),
        ]

    def __str__(self):
        return self.title


class Bucket(TimeStampedModel, OrderedModel):
    """A column within a plan that groups tasks (e.g. 'To Do', 'In Progress')."""

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

    def __str__(self):
        return self.title
```

Let's break down the design decisions.

#### Two User FKs: `owner` vs `created_by`

A plan has two FK relationships to User:

- **`owner`** — the person currently responsible for the plan. Can change over time. Uses `blank=True` because it's editable in forms.
- **`created_by`** — who originally created the plan. Set once in the view, never shown in forms. No `blank=True` — forms shouldn't set this field.

Both use `SET_NULL` because deleting a user shouldn't delete their plans. The plans belong to a team, not a person.

#### `settings.AUTH_USER_MODEL` instead of direct import

```python
from django.conf import settings

owner = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
```

Never import your User model directly in a FK declaration. `settings.AUTH_USER_MODEL` is a string reference (`"accounts.User"`) that Django resolves at migration time. This avoids circular imports and is the standard pattern for all FK/M2M relationships to the user model.

#### `TextChoices` for visibility

```python
class Visibility(models.TextChoices):
    PRIVATE = "private", "Private"
    PUBLIC = "public", "Public"
```

We use `TextChoices` here because visibility is a categorical label — there's no meaningful ordering between "private" and "public". Compare this to `IntegerChoices`, which we'll use for task priority where ordering matters.

#### `on_delete=models.CASCADE` for `team`

If a team is deleted, its plans go with it. A plan without a team is meaningless — there's no one to see it or work on it.

#### Composite index

```python
models.Index(fields=["team", "-created_at"], name="idx_plan_team_created"),
```

This supports the most common query: "show me all plans for this team, newest first." The minus sign means descending order. Without this index, the database would need a full table scan followed by a sort.

Always name your indexes explicitly (`name="idx_..."`) rather than letting Django auto-generate names — it makes migration files and database inspection more readable.

#### Wiring the QuerySet as a Manager

```python
objects = PlanQuerySet.as_manager()
```

This single line replaces the default manager with one backed by our custom queryset. Now `Plan.objects.for_user(user)` works directly — no separate manager class needed.

#### Bucket: Inheriting Two Abstract Models

```python
class Bucket(TimeStampedModel, OrderedModel):
```

Python supports multiple inheritance, and Django abstract models are designed for it. `Bucket` gets `created_at` and `modified_at` from `TimeStampedModel`, plus `position` from `OrderedModel`.

**`Meta` inheritance** — note `class Meta(OrderedModel.Meta):`. This inherits `OrderedModel`'s default ordering (`["position"]`). Without it, Bucket would lose that ordering.

#### Deferred Unique Constraints

```python
models.UniqueConstraint(
    fields=["plan", "position"],
    name="unique_bucket_position",
    deferrable=models.Deferrable.DEFERRED,
)
```

This ensures no two buckets in the same plan can share the same position. But why `DEFERRED`?

Consider drag-and-drop reordering. A user drags Bucket B from position 2 to position 0. The update needs to shift positions: 0→1, 1→2, and B→0. With an immediate constraint, the first UPDATE would violate uniqueness — two buckets temporarily have the same position.

`DEFERRED` tells PostgreSQL to check the constraint at commit time, not after each statement. Inside a transaction, intermediate states can violate the constraint as long as the final state is valid:

```python
from django.db import transaction

def reorder_buckets(plan, ordered_bucket_ids):
    with transaction.atomic():
        for position, bucket_id in enumerate(ordered_bucket_ids):
            Bucket.objects.filter(pk=bucket_id, plan=plan).update(position=position)
```

### Step 3: Plan Factories

Create `apps/plans/tests/factories.py`:

```python
import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import TeamFactory
from apps.plans.models import Bucket, Plan


class PlanFactory(DjangoModelFactory):
    class Meta:
        model = Plan

    title = factory.Sequence(lambda n: f"Plan {n}")
    description = ""
    team = factory.SubFactory(TeamFactory)
    owner = factory.LazyAttribute(lambda obj: obj.team.owner)
    created_by = factory.LazyAttribute(lambda obj: obj.owner)
    visibility = Plan.Visibility.PRIVATE


class BucketFactory(DjangoModelFactory):
    class Meta:
        model = Bucket

    plan = factory.SubFactory(PlanFactory)
    title = factory.Sequence(lambda n: f"Bucket {n}")
    position = factory.Sequence(lambda n: n)
```

**`LazyAttribute` for derived FKs** — `owner` defaults to the team's owner, and `created_by` defaults to the owner. This means `PlanFactory()` produces a consistent plan without any arguments — the owner, creator, and team all connect logically.

**`BucketFactory.position`** uses `Sequence` to auto-increment. Each factory call gets the next integer (0, 1, 2, ...), which works well for the unique constraint — as long as each bucket belongs to a different plan, or you manually set positions.

### Step 4: Plan Tests

Create `apps/plans/tests/test_models.py`:

```python
from django.test import TestCase

from apps.plans.tests.factories import BucketFactory, PlanFactory


class TestPlan(TestCase):
    def test_str(self):
        plan = PlanFactory(title="Sprint 42")
        assert str(plan) == "Sprint 42"


class TestBucket(TestCase):
    def test_str(self):
        bucket = BucketFactory(title="In Progress")
        assert str(bucket) == "In Progress"
```

These tests are short because `Plan` and `Bucket` have no custom business logic — they're data containers. The only custom code is `__str__`, so that's what we test.

Create `apps/plans/tests/test_querysets.py`:

```python
import pytest

from apps.accounts.tests.factories import MembershipFactory, UserFactory
from apps.plans.models import Plan
from apps.plans.tests.factories import BucketFactory, PlanFactory


@pytest.mark.django_db
class TestPlanQuerySetForUser:
    """PlanQuerySet.for_user() returns plans visible through team membership."""

    def test_returns_plans_for_team_member(self):
        membership = MembershipFactory()
        plan = PlanFactory(team=membership.team)

        result = Plan.objects.for_user(membership.user)

        assert plan in result

    def test_excludes_plans_from_other_teams(self):
        user = UserFactory()
        plan = PlanFactory()  # belongs to a different team

        result = Plan.objects.for_user(user)

        assert plan not in result

    def test_no_duplicates_when_user_in_multiple_roles(self):
        """A user who is both owner and member should see each plan once."""
        membership = MembershipFactory()
        plan = PlanFactory(team=membership.team)
        # User also owns the team — could cause duplicate JOINs
        plan.team.owner = membership.user
        plan.team.save()

        result = Plan.objects.for_user(membership.user)

        assert list(result.filter(pk=plan.pk)).count(plan) == 1


@pytest.mark.django_db
class TestPlanQuerySetWithTaskCounts:
    """PlanQuerySet.with_task_counts() annotates total and completed counts."""

    def test_counts_tasks_across_buckets(self):
        plan = PlanFactory()
        bucket_a = BucketFactory(plan=plan, position=0)
        bucket_b = BucketFactory(plan=plan, position=1)

        from apps.tasks.tests.factories import TaskFactory

        TaskFactory(bucket=bucket_a)
        TaskFactory(bucket=bucket_b)

        annotated = Plan.objects.with_task_counts().get(pk=plan.pk)

        assert annotated.task_count == 2
        assert annotated.completed_task_count == 0

    def test_counts_completed_tasks(self):
        plan = PlanFactory()
        bucket = BucketFactory(plan=plan, position=0)

        from apps.tasks.tests.factories import TaskFactory

        TaskFactory(bucket=bucket, progress=100)
        TaskFactory(bucket=bucket, progress=50)

        annotated = Plan.objects.with_task_counts().get(pk=plan.pk)

        assert annotated.task_count == 2
        assert annotated.completed_task_count == 1

    def test_zero_counts_when_no_tasks(self):
        plan = PlanFactory()

        annotated = Plan.objects.with_task_counts().get(pk=plan.pk)

        assert annotated.task_count == 0
        assert annotated.completed_task_count == 0
```

**Why inline imports in `TestPlanQuerySetWithTaskCounts`?** — The `with_task_counts()` queryset spans from `Plan` through `Bucket` to `Task`. Testing it requires creating tasks, which means importing `TaskFactory`. But `apps.plans` shouldn't depend on `apps.tasks` at the module level — the dependency goes the other way (tasks depend on plans). Using an inline import inside test methods keeps the import graph clean while still allowing us to test the cross-app annotation.

**Test structure mirrors implementation** — model tests go in `test_models.py`, queryset tests go in `test_querysets.py`. This makes it easy to find tests: if you're working on `querysets.py`, the tests are in `test_querysets.py`.

---

## Tasks App

This is the heart of the application. Seven models, but the patterns are all things we've already seen — FKs, M2M through models, `OrderedModel`, `TextChoices`/`IntegerChoices`, and `UniqueConstraint`.

### Step 1: Task QuerySet

Create `apps/tasks/querysets.py`:

```python
from django.db import models
from django.utils import timezone


class TaskQuerySet(models.QuerySet):
    """Custom queryset for Task with scoping, filtering, and annotation helpers."""

    def for_user(self, user):
        """Return tasks assigned to this user."""
        return self.filter(assignments__user=user).distinct()

    def overdue(self):
        """Return incomplete tasks past their due date."""
        return self.filter(
            due_date__lt=timezone.now().date(),
            progress__lt=100,
        )

    def with_checklist_counts(self):
        """Annotate each task with total and completed checklist item counts."""
        return self.annotate(
            checklist_total=models.Count("checklist_items", distinct=True),
            checklist_done=models.Count(
                "checklist_items",
                filter=models.Q(checklist_items__is_completed=True),
                distinct=True,
            ),
        )

    def search(self, query):
        """Basic title/description search. Will be replaced with FTS in Chapter 14."""
        return self.filter(
            models.Q(title__icontains=query) | models.Q(description__icontains=query)
        )
```

**`for_user()`** — similar to `PlanQuerySet.for_user()`, but scoped through the `Assignment` through model. Returns all tasks where this user has an assignment record.

**`overdue()`** — returns incomplete tasks past their due date. Uses `timezone.now().date()` (not `datetime.date.today()`) to respect the `TIME_ZONE` setting.

**`with_checklist_counts()`** — annotates each task with total and completed checklist items. This powers the "3/5 done" display you see on task cards.

**`search()`** — a simple `icontains` search across title and description. `Q` objects let you combine conditions with OR (`|`). This is a placeholder — we'll replace it with PostgreSQL full-text search in a later chapter for better performance and features like stemming and ranking.

### Step 2: Task and Related Models

Create `apps/tasks/models.py`:

```python
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import OrderedModel, TimeStampedModel

from .querysets import TaskQuerySet


class Task(TimeStampedModel):
    """A task within a bucket. The central model of the application."""

    class Priority(models.IntegerChoices):
        URGENT = 1, "Urgent"
        IMPORTANT = 3, "Important"
        MEDIUM = 5, "Medium"
        LOW = 9, "Low"

    class Progress(models.IntegerChoices):
        NOT_STARTED = 0, "Not started"
        IN_PROGRESS = 50, "In progress"
        COMPLETED = 100, "Completed"

    bucket = models.ForeignKey(
        "plans.Bucket",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.PositiveSmallIntegerField(
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    progress = models.PositiveSmallIntegerField(
        choices=Progress.choices,
        default=Progress.NOT_STARTED,
    )
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Assignment",
        related_name="assigned_tasks",
        blank=True,
    )
    labels = models.ManyToManyField(
        "Label",
        related_name="tasks",
        blank=True,
    )

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["bucket", "-created_at"], name="idx_task_bucket_created"
            ),
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
    def is_overdue(self) -> bool:
        """True if the task is past its due date and not yet completed."""
        return (
            self.due_date is not None
            and self.due_date < timezone.now().date()
            and self.progress < self.Progress.COMPLETED
        )

    def mark_complete(self) -> None:
        """Set this task to completed with a timestamp."""
        self.progress = self.Progress.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["progress", "completed_at"])
```

#### `IntegerChoices` with Gaps

```python
class Priority(models.IntegerChoices):
    URGENT = 1, "Urgent"
    IMPORTANT = 3, "Important"
    MEDIUM = 5, "Medium"
    LOW = 9, "Low"
```

We use `IntegerChoices` (not `TextChoices`) because priority has a meaningful order — Urgent (1) is higher than Low (9). The values skip numbers (1, 3, 5, 9) to leave room for future priorities without rewriting the existing ones. If we later need a "Critical" level above Urgent, we could use 0. If we need something between Medium and Low, we could use 7.

`Progress` follows the same pattern — 0, 50, 100 represent percentage-like checkpoints.

#### `null=True` vs `blank=True` — Why They're Different

This model demonstrates several combinations:

| Field | `null` | `blank` | Why |
|---|---|---|---|
| `title` | No | No | Required — every task needs a title |
| `description` | No | Yes | Optional text — `blank=True` allows empty strings, but we never store NULL for text fields |
| `due_date` | Yes | Yes | Optional date — NULL means "no due date set" |
| `completed_at` | Yes | Yes | Computed — NULL means "not yet completed" |
| `created_by` | Yes | No | Set in the view, not in forms — `null=True` because `SET_NULL` requires it |
| `assignees` (M2M) | No | Yes | Zero selections is fine — never use `null=True` on M2M |

The rule: `null=True` means the database column accepts NULL. `blank=True` means forms allow an empty value. Text fields (`CharField`, `TextField`) should never use `null=True` — use `blank=True` and store empty strings instead. Otherwise you get two representations of "no value" (NULL and `""`) and every filter has to check both.

#### Partial Index

```python
models.Index(
    fields=["progress"],
    name="idx_task_incomplete",
    condition=models.Q(progress__lt=100),
),
```

A partial index only indexes rows that match the condition. Most queries care about incomplete tasks ("show me what's left to do"), not completed ones. A partial index on `progress < 100` is smaller and faster than indexing every row — completed tasks (which grow over time) don't bloat the index.

#### Fat Model Methods

```python
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
    self.save(update_fields=["progress", "completed_at"])
```

Domain logic belongs on the model, not in views. This is the "fat models, thin views" principle.

**`is_overdue`** is a property because it's a computed boolean — no side effects, no database writes. It checks three conditions: has a due date, the due date has passed, and the task isn't completed.

**`mark_complete()`** is a method because it mutates state and writes to the database. It sets both `progress` and `completed_at` in one operation.

**`update_fields`** — instead of `self.save()`, we use `self.save(update_fields=["progress", "completed_at"])`. This generates `UPDATE tasks_task SET progress=100, completed_at=... WHERE id=...` instead of updating every column. It's faster and avoids race conditions where two users edit different fields simultaneously.

Note: our `TimeStampedModel.save()` override automatically adds `modified_at` to `update_fields`, so the timestamp stays current even with targeted updates.

### Step 3: Supporting Models

The remaining models follow patterns we've already established:

```python
class Assignment(TimeStampedModel):
    """Explicit M2M through model linking tasks to assigned users."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task", "user"],
                name="unique_task_assignment",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.task}"
```

**Assignment** — the M2M through model for task-to-user. Like `Membership` in Chapter 5, we use an explicit through model so we can add fields later (assigned_by, assigned_at). The `UniqueConstraint` prevents assigning the same user twice.

Both FKs use `CASCADE` — if the task is deleted, its assignments go too. If the user is deleted, their assignments go too. An assignment without both a task and a user is meaningless.

```python
class ChecklistItem(TimeStampedModel, OrderedModel):
    """A checklist item within a task."""

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
        indexes = [
            models.Index(fields=["task", "position"], name="idx_checklist_task_pos"),
        ]

    def __str__(self):
        return self.title
```

**ChecklistItem** — inherits `OrderedModel` just like `Bucket`, with the same deferred unique constraint pattern for drag-and-drop reordering. `is_completed` is a `BooleanField` with a default — booleans should never be nullable unless you genuinely need three states (True/False/Unknown).

```python
class Label(TimeStampedModel):
    """A colored label scoped to a plan, shared across that plan's tasks."""

    plan = models.ForeignKey(
        "plans.Plan",
        on_delete=models.CASCADE,
        related_name="labels",
    )
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default="#6B7280")  # hex color

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "name"],
                name="unique_label_per_plan",
            ),
        ]

    def __str__(self):
        return self.name
```

**Label** — scoped to a plan, not global. The `UniqueConstraint` on `["plan", "name"]` means each plan can have a label called "Bug", but two different plans can both have their own "Bug" label. This is a compound uniqueness constraint — the combination must be unique, not each field individually.

Labels connect to tasks via `ManyToManyField` on `Task`. Since we don't need extra fields on the relationship, we let Django create the join table implicitly (no `through` model).

```python
class Comment(TimeStampedModel):
    """A comment on a task."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="comments",
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"], name="idx_comment_task_created"),
        ]

    def __str__(self):
        return f"Comment by {self.created_by} on {self.task}"
```

**Comment** — ordered by `created_at` (oldest first, like a conversation). `created_by` uses `SET_NULL` so comments survive when a user is deleted — the comment text is still valuable even if the author is gone.

### `related_name` Conventions

Every FK and M2M in this chapter sets `related_name` explicitly. The pattern:

| Relationship | `related_name` | Usage |
|---|---|---|
| `Task.bucket → Bucket` | `"tasks"` | `bucket.tasks.all()` |
| `Task.created_by → User` | `"created_tasks"` | `user.created_tasks.all()` |
| `Task.assignees → User` | `"assigned_tasks"` | `user.assigned_tasks.all()` |
| `Comment.task → Task` | `"comments"` | `task.comments.all()` |
| `Label.plan → Plan` | `"labels"` | `plan.labels.all()` |

When a model has multiple FKs to the same target (like `Task` having both `created_by` and `assignees` pointing to User), you **must** set `related_name` — Django can't auto-generate unique reverse names.

### Step 4: Task Factories

Create `apps/tasks/tests/factories.py`:

```python
import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.models import Assignment, ChecklistItem, Comment, Label, Task


class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    bucket = factory.SubFactory(BucketFactory)
    title = factory.Sequence(lambda n: f"Task {n}")
    description = ""
    priority = Task.Priority.MEDIUM
    progress = Task.Progress.NOT_STARTED
    created_by = factory.SubFactory(UserFactory)


class AssignmentFactory(DjangoModelFactory):
    class Meta:
        model = Assignment

    task = factory.SubFactory(TaskFactory)
    user = factory.SubFactory(UserFactory)


class ChecklistItemFactory(DjangoModelFactory):
    class Meta:
        model = ChecklistItem

    task = factory.SubFactory(TaskFactory)
    title = factory.Sequence(lambda n: f"Checklist item {n}")
    position = factory.Sequence(lambda n: n)
    is_completed = False


class LabelFactory(DjangoModelFactory):
    class Meta:
        model = Label

    plan = factory.SubFactory(PlanFactory)
    name = factory.Sequence(lambda n: f"Label {n}")
    color = "#6B7280"


class CommentFactory(DjangoModelFactory):
    class Meta:
        model = Comment

    task = factory.SubFactory(TaskFactory)
    created_by = factory.SubFactory(UserFactory)
    body = factory.Sequence(lambda n: f"Comment body {n}")
```

Nothing new here — the same `SubFactory` and `Sequence` patterns from earlier chapters. Each factory creates everything it needs: `TaskFactory()` creates a bucket, which creates a plan, which creates a team, which creates an owner user. One line of factory code can create an entire object graph.

### Step 5: Task Model Tests

Create `apps/tasks/tests/test_models.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.tasks.models import Task
from apps.tasks.tests.factories import (
    AssignmentFactory,
    ChecklistItemFactory,
    CommentFactory,
    LabelFactory,
    TaskFactory,
)


@pytest.mark.django_db
class TestTaskStr:
    def test_str(self):
        task = TaskFactory(title="Fix login bug")
        assert str(task) == "Fix login bug"


@pytest.mark.django_db
class TestAssignmentStr:
    def test_str(self):
        assignment = AssignmentFactory()
        expected = f"{assignment.user} → {assignment.task}"
        assert str(assignment) == expected


@pytest.mark.django_db
class TestChecklistItemStr:
    def test_str(self):
        item = ChecklistItemFactory(title="Write docs")
        assert str(item) == "Write docs"


@pytest.mark.django_db
class TestLabelStr:
    def test_str(self):
        label = LabelFactory(name="Bug")
        assert str(label) == "Bug"


@pytest.mark.django_db
class TestCommentStr:
    def test_str(self):
        comment = CommentFactory()
        expected = f"Comment by {comment.created_by} on {comment.task}"
        assert str(comment) == expected


@pytest.mark.django_db
class TestTaskIsOverdue:
    """Task.is_overdue property logic."""

    def test_overdue_when_past_due_and_incomplete(self):
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

    def test_not_overdue_when_due_today(self):
        task = TaskFactory(
            due_date=timezone.now().date(),
            progress=Task.Progress.NOT_STARTED,
        )
        assert task.is_overdue is False

    def test_not_overdue_when_due_in_future(self):
        task = TaskFactory(
            due_date=timezone.now().date() + timedelta(days=7),
            progress=Task.Progress.NOT_STARTED,
        )
        assert task.is_overdue is False

    def test_not_overdue_when_no_due_date(self):
        task = TaskFactory(due_date=None, progress=Task.Progress.NOT_STARTED)
        assert task.is_overdue is False


@pytest.mark.django_db
class TestTaskMarkComplete:
    """Task.mark_complete() sets progress and timestamp."""

    def test_sets_progress_to_completed(self):
        task = TaskFactory(progress=Task.Progress.IN_PROGRESS)
        task.mark_complete()
        task.refresh_from_db()
        assert task.progress == Task.Progress.COMPLETED

    def test_sets_completed_at_timestamp(self):
        task = TaskFactory()
        assert task.completed_at is None

        task.mark_complete()
        task.refresh_from_db()

        assert task.completed_at is not None

    def test_persists_to_database(self):
        task = TaskFactory()
        task.mark_complete()

        reloaded = Task.objects.get(pk=task.pk)
        assert reloaded.progress == Task.Progress.COMPLETED
        assert reloaded.completed_at is not None
```

**`__str__` tests** — one test per model, same pattern as Chapter 5. These are short because each `__str__` is a one-liner, but they're still worth writing: the formatting strings (`f"{user} → {task}"`, `f"Comment by {created_by} on {task}"`) are code we wrote, not behavior we inherited.

**Testing `is_overdue`** — five test cases covering every branch: past due + incomplete (True), past due + completed (False), due today (False), future due (False), no due date (False). This is thorough property testing — every combination of inputs that could change the outcome.

**Testing `mark_complete()`** — three tests: it sets progress, it sets the timestamp, and it actually persists to the database. The `refresh_from_db()` call reloads the object from the database, proving the save worked. The third test (`test_persists_to_database`) creates a fresh ORM instance from the database to double-check.

**What we don't test** — field declarations, `auto_now` timestamps, `default` values, uniqueness constraints, or cascade behavior. Those are Django features configured declaratively; the framework's own test suite already covers them.

### Step 6: Task QuerySet Tests

Create `apps/tasks/tests/test_querysets.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.tasks.models import Task
from apps.tasks.tests.factories import AssignmentFactory, ChecklistItemFactory, TaskFactory


@pytest.mark.django_db
class TestTaskQuerySetForUser:
    """TaskQuerySet.for_user() returns tasks assigned to a user."""

    def test_returns_assigned_tasks(self):
        assignment = AssignmentFactory()

        result = Task.objects.for_user(assignment.user)

        assert assignment.task in result

    def test_excludes_unassigned_tasks(self):
        assignment = AssignmentFactory()
        other_task = TaskFactory()

        result = Task.objects.for_user(assignment.user)

        assert other_task not in result

    def test_no_duplicates_with_multiple_assignments(self):
        """A task with multiple assignees shouldn't appear multiple times for one user."""
        assignment = AssignmentFactory()
        # Add a second assignee to the same task
        AssignmentFactory(task=assignment.task)

        result = Task.objects.for_user(assignment.user)

        assert result.filter(pk=assignment.task.pk).count() == 1


@pytest.mark.django_db
class TestTaskQuerySetOverdue:
    """TaskQuerySet.overdue() returns incomplete tasks past their due date."""

    def test_includes_past_due_incomplete(self):
        task = TaskFactory(
            due_date=timezone.now().date() - timedelta(days=1),
            progress=Task.Progress.NOT_STARTED,
        )

        assert task in Task.objects.overdue()

    def test_excludes_completed(self):
        task = TaskFactory(
            due_date=timezone.now().date() - timedelta(days=1),
            progress=Task.Progress.COMPLETED,
        )

        assert task not in Task.objects.overdue()

    def test_excludes_future_due(self):
        task = TaskFactory(
            due_date=timezone.now().date() + timedelta(days=1),
            progress=Task.Progress.NOT_STARTED,
        )

        assert task not in Task.objects.overdue()


@pytest.mark.django_db
class TestTaskQuerySetWithChecklistCounts:
    """TaskQuerySet.with_checklist_counts() annotates checklist totals."""

    def test_counts_checklist_items(self):
        task = TaskFactory()
        ChecklistItemFactory(task=task, position=0, is_completed=True)
        ChecklistItemFactory(task=task, position=1, is_completed=False)
        ChecklistItemFactory(task=task, position=2, is_completed=True)

        annotated = Task.objects.with_checklist_counts().get(pk=task.pk)

        assert annotated.checklist_total == 3
        assert annotated.checklist_done == 2

    def test_zero_when_no_checklist(self):
        task = TaskFactory()

        annotated = Task.objects.with_checklist_counts().get(pk=task.pk)

        assert annotated.checklist_total == 0
        assert annotated.checklist_done == 0


@pytest.mark.django_db
class TestTaskQuerySetSearch:
    """TaskQuerySet.search() filters by title and description."""

    def test_matches_title(self):
        task = TaskFactory(title="Fix login bug")

        result = Task.objects.search("login")

        assert task in result

    def test_matches_description(self):
        task = TaskFactory(description="Users cannot log in after password reset")

        result = Task.objects.search("password reset")

        assert task in result

    def test_excludes_non_matching(self):
        TaskFactory(title="Fix login bug", description="Authentication issue")

        result = Task.objects.search("dashboard")

        assert result.count() == 0
```

Each queryset method gets its own test class. The tests follow a pattern: create data, call the method, assert what's included and what's excluded.

**`TestTaskQuerySetForUser`** — tests inclusion, exclusion, and the no-duplicates edge case. The duplicate test creates a task with two assignees and verifies the task appears only once for the first assignee.

**`TestTaskQuerySetOverdue`** — mirrors the `is_overdue` property tests, but at the queryset level. This tests filtering (which rows come back), not computation (what a property returns). The distinction matters — `overdue()` runs in SQL, `is_overdue` runs in Python.

---

## Step 7: Generate Migrations

With both apps' models written, generate the migrations:

```bash
uv run python manage.py makemigrations plans tasks
```

This creates:
- `apps/plans/migrations/0001_initial.py` — Plan and Bucket tables
- `apps/tasks/migrations/0001_initial.py` — Task, Assignment, ChecklistItem, Label, Comment tables plus indexes and constraints

Apply them:

```bash
uv run python manage.py migrate
```

## Step 8: Run the Tests

```bash
uv run pytest apps/plans/ apps/tasks/ -v
```

All tests should pass.

---

## Checkpoint

Before moving on, verify:

- [ ] `uv run pytest -v` passes all tests
- [ ] `uv run ruff check apps/ config/` reports no lint errors
- [ ] `uv run python manage.py migrate` completes with no errors
- [ ] Migrations exist for both apps: `apps/plans/migrations/0001_initial.py` and `apps/tasks/migrations/0001_initial.py`

**Next:** [Chapter 7 — Attachments & Notifications](07-attachments-notifications.md)
