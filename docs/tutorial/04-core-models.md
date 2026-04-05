# Chapter 4 — Core Abstract Models

## Goal

By the end of this chapter you'll have:
- Two reusable abstract base models: `TimeStampedModel` and `OrderedModel`
- Tests that prove abstract models work correctly (including edge cases)
- An understanding of abstract models, `auto_now`/`auto_now_add`, and why these belong in a `core` app

---

## Why Abstract Models?

Almost every model in Planly needs timestamps — when it was created, when it was last modified. Several models also need a `position` field for drag-and-drop ordering (buckets in a plan, tasks in a bucket, checklist items in a task).

You could add these fields to every model individually:

```python
class Plan(models.Model):
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

class Bucket(models.Model):
    title = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
```

But that's repetitive and error-prone. If you need to fix a bug in the timestamp behavior (we will — see the `update_fields` gotcha below), you'd have to fix it in every model.

Abstract models solve this. They define fields and behavior once, and concrete models inherit from them:

```python
class Plan(TimeStampedModel):
    title = models.CharField(max_length=255)

class Bucket(TimeStampedModel, OrderedModel):
    title = models.CharField(max_length=255)
```

### What makes a model "abstract"?

Setting `abstract = True` in the model's `Meta` class tells Django: "Don't create a database table for this model. Just let other models inherit its fields." The fields are copied into each child model's table — there's no JOIN, no performance cost.

### Why a `core` app?

Abstract base models don't belong to any specific domain — they're shared infrastructure. The `core` app is where we put cross-cutting concerns: abstract models, custom middleware, template tags, and anything else that multiple apps need. The `core` app has no database tables, no views, and no URLs of its own.

---

## Step 1: Write the Tests First

This is our first real TDD chapter. We write the tests before the implementation. The workflow:

1. **Red** — write tests that fail (because the code doesn't exist yet)
2. **Green** — write the minimum code to make the tests pass
3. **Refactor** — clean up while keeping tests green

### The challenge with testing abstract models

Abstract models don't have database tables, so you can't create instances of them directly. The solution: define **concrete test models** that inherit from the abstract base, and test those.

With `--no-migrations` in our pytest config, pytest-django creates tables directly from model definitions — including these test-only models. They exist in the test database but never in production.

Create `apps/core/tests/test_models.py`:

```python
from django.db import models
from django.test import TestCase
from django.utils import timezone

from apps.core.models import OrderedModel, TimeStampedModel


# Concrete models for testing abstract bases — these get real tables
# via pytest-django's --no-migrations flag (creates tables from model defs).
class ConcreteTimeStamped(TimeStampedModel):
    title = models.CharField(max_length=100)

    class Meta:
        app_label = "core"


class ConcreteOrdered(OrderedModel):
    title = models.CharField(max_length=100)

    class Meta(OrderedModel.Meta):
        app_label = "core"


class ConcreteTimeStampedOrdered(TimeStampedModel, OrderedModel):
    """Tests that both abstract models can be composed together."""

    title = models.CharField(max_length=100)

    class Meta(OrderedModel.Meta):
        app_label = "core"


class TestTimeStampedModel(TestCase):
    def test_created_at_set_on_create(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        assert obj.created_at is not None
        assert obj.created_at <= timezone.now()

    def test_modified_at_set_on_create(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        assert obj.modified_at is not None

    def test_modified_at_changes_on_save(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        original_updated = obj.modified_at
        obj.title = "changed"
        obj.save()
        obj.refresh_from_db()
        assert obj.modified_at > original_updated

    def test_created_at_unchanged_on_save(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        original_created = obj.created_at
        obj.title = "changed"
        obj.save()
        obj.refresh_from_db()
        assert obj.created_at == original_created

    def test_modified_at_changes_with_update_fields(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        original_updated = obj.modified_at
        obj.title = "changed"
        obj.save(update_fields=["title"])
        obj.refresh_from_db()
        assert obj.modified_at > original_updated

    def test_is_abstract(self):
        assert TimeStampedModel._meta.abstract is True


class TestOrderedModel(TestCase):
    def test_default_position_is_zero(self):
        obj = ConcreteOrdered.objects.create(title="first")
        assert obj.position == 0

    def test_position_can_be_set(self):
        obj = ConcreteOrdered.objects.create(title="second", position=5)
        assert obj.position == 5

    def test_ordering_by_position(self):
        ConcreteOrdered.objects.create(title="third", position=3)
        ConcreteOrdered.objects.create(title="first", position=1)
        ConcreteOrdered.objects.create(title="second", position=2)
        titles = list(ConcreteOrdered.objects.values_list("title", flat=True))
        assert titles == ["first", "second", "third"]

    def test_position_is_indexed(self):
        field = ConcreteOrdered._meta.get_field("position")
        assert field.db_index is True

    def test_is_abstract(self):
        assert OrderedModel._meta.abstract is True


class TestComposedModels(TestCase):
    def test_has_all_fields(self):
        obj = ConcreteTimeStampedOrdered.objects.create(title="test", position=1)
        assert obj.created_at is not None
        assert obj.modified_at is not None
        assert obj.position == 1
```

### Why these specific tests?

Each test targets a specific behavior:

**TestTimeStampedModel:**
- `test_created_at_set_on_create` — verifies `auto_now_add` works
- `test_modified_at_set_on_create` — verifies `auto_now` is set on first save
- `test_modified_at_changes_on_save` — verifies `auto_now` updates on each save
- `test_created_at_unchanged_on_save` — verifies `auto_now_add` is write-once
- `test_modified_at_changes_with_update_fields` — catches the `update_fields` bug (see below)
- `test_is_abstract` — ensures the model won't accidentally get a table

**TestOrderedModel:**
- `test_default_position_is_zero` — verifies the default
- `test_position_can_be_set` — explicit position works
- `test_ordering_by_position` — `Meta.ordering` sorts querysets by position
- `test_position_is_indexed` — the database index exists for query performance
- `test_is_abstract` — no accidental table

**TestComposedModels:**
- `test_has_all_fields` — verifies multiple inheritance works (both abstracts on one model)

### Why `app_label = "core"`?

The concrete test models need an `app_label` so Django knows which app they belong to. Without it, Django can't create the database table. We use `"core"` since that's where the abstract models live.

### Why `class Meta(OrderedModel.Meta)`?

`ConcreteOrdered` inherits `Meta` from `OrderedModel.Meta` to preserve the `ordering = ["position"]` setting. If we wrote `class Meta:` without the inheritance, we'd lose the ordering and `test_ordering_by_position` would fail.

---

## Step 2: Run the Tests (Red)

```bash
uv run pytest apps/core/tests/test_models.py -v
```

```
ImportError: cannot import name 'OrderedModel' from 'core.models'
```

The test fails because the models don't exist yet. This is the "red" step — we've confirmed the tests are checking the right things.

---

## Step 3: Implement the Models (Green)

Create `apps/core/models.py`:

```python
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base that adds created_at and modified_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Ensure modified_at is always written, even when save() is called
        # with update_fields. Without this, save(update_fields=["title"])
        # would skip the auto_now field entirely.
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "modified_at"}
        super().save(*args, **kwargs)


class OrderedModel(models.Model):
    """Abstract base that adds a position field for drag-and-drop ordering."""

    position = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["position"]
```

### `auto_now_add` vs `auto_now`

| Option | When it sets the value | Use case |
|---|---|---|
| `auto_now_add=True` | Only on first save (INSERT) | `created_at` — the timestamp never changes |
| `auto_now=True` | On every save (INSERT and UPDATE) | `modified_at` — the timestamp updates whenever the row changes |

Both options make the field non-editable — you can't pass a value to `create()` or set it manually. This is intentional: timestamps should be managed by the system, not by application code.

### The `update_fields` Gotcha

This is the kind of bug that costs teams hours. Here's the scenario:

```python
task.title = "Updated title"
task.save(update_fields=["title"])
```

Using `update_fields` is a best practice — it generates a leaner `UPDATE` query that only touches the specified columns. But Django's `auto_now` fields are **not** automatically included in `update_fields`. The `modified_at` column stays unchanged in the database, silently lying about when the row was last modified.

Our `save()` override fixes this by injecting `modified_at` into `update_fields` whenever it's provided:

```python
def save(self, *args, **kwargs):
    if kwargs.get("update_fields") is not None:
        kwargs["update_fields"] = {*kwargs["update_fields"], "modified_at"}
    super().save(*args, **kwargs)
```

We use `{*kwargs["update_fields"], "modified_at"}` — a set comprehension that merges the original fields with `modified_at`. A set avoids duplicates if `modified_at` is already included.

### Why `PositiveIntegerField` for position?

Position should never be negative — it represents an index in an ordered list. `PositiveIntegerField` enforces this at the database level (adds a `CHECK` constraint). The `default=0` means new items start at position zero if no position is specified.

### Why `db_index=True`?

Queries like "get all buckets for this plan, ordered by position" are the most common read pattern for ordered models. Without an index, the database does a full table scan and sorts in memory. With an index, it reads rows in order directly from the index. For a plan with 50 buckets this doesn't matter, but it's good practice to index any field you `ORDER BY`.

### Why `ordering = ["position"]` in Meta?

This sets the **default ordering** for all querysets on models that inherit `OrderedModel`. Without it, you'd have to remember to add `.order_by("position")` every time you query. Default ordering means `Bucket.objects.all()` returns buckets in position order automatically.

---

## Step 4: Run the Tests (Green)

```bash
uv run pytest apps/core/tests/test_models.py -v
```

```
apps/core/tests/test_models.py::TestTimeStampedModel::test_created_at_set_on_create PASSED
apps/core/tests/test_models.py::TestTimeStampedModel::test_modified_at_set_on_create PASSED
apps/core/tests/test_models.py::TestTimeStampedModel::test_modified_at_changes_on_save PASSED
apps/core/tests/test_models.py::TestTimeStampedModel::test_created_at_unchanged_on_save PASSED
apps/core/tests/test_models.py::TestTimeStampedModel::test_modified_at_changes_with_update_fields PASSED
apps/core/tests/test_models.py::TestTimeStampedModel::test_is_abstract PASSED
apps/core/tests/test_models.py::TestOrderedModel::test_default_position_is_zero PASSED
apps/core/tests/test_models.py::TestOrderedModel::test_position_can_be_set PASSED
apps/core/tests/test_models.py::TestOrderedModel::test_ordering_by_position PASSED
apps/core/tests/test_models.py::TestOrderedModel::test_position_is_indexed PASSED
apps/core/tests/test_models.py::TestOrderedModel::test_is_abstract PASSED
apps/core/tests/test_models.py::TestComposedModels::test_has_all_fields PASSED
```

All 12 tests pass.

> **Note:** If you see errors about columns not existing, run `uv run pytest --create-db` once to rebuild the test database. The `--reuse-db` flag caches the database schema between runs, so when you add new models or rename fields, you need to force a rebuild.

---

## How These Models Will Be Used

In the coming chapters, every model will inherit from `TimeStampedModel`:

```python
# Chapter 5 — User extends AbstractUser directly (it already has date_joined/last_login)
class User(AbstractUser):
    ...

# Chapter 5 — Team and Membership get timestamps
class Team(TimeStampedModel):
    ...

# Chapter 6
class Plan(TimeStampedModel):
    ...

class Bucket(TimeStampedModel, OrderedModel):
    ...

# Chapter 6
class Task(TimeStampedModel, OrderedModel):
    ...

class ChecklistItem(TimeStampedModel, OrderedModel):
    ...
```

Most models inherit from `TimeStampedModel`. The exception is `User` — `AbstractUser` already provides `date_joined` and `last_login`, so adding timestamps would be redundant. Models that support drag-and-drop reordering inherit from both. The `save()` override on `TimeStampedModel` and the default ordering on `OrderedModel` work together seamlessly through Python's multiple inheritance.

---

## Checkpoint

Before moving on, verify:

- [ ] `uv run pytest -v` passes all 14 tests (12 model + 2 settings)
- [ ] `uv run ruff check apps/ config/` reports no lint errors
- [ ] `apps/core/models.py` contains only abstract models (no tables in the database)

**Next:** [Chapter 5 — Accounts: Users & Teams](05-accounts.md)
