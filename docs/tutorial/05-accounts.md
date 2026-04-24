# Chapter 5 — Accounts: Users & Teams

## Goal

By the end of this chapter you'll have:
- A custom user model with employee ID as the primary key and login identifier
- A custom `UserManager` for user creation
- `Team` and `Membership` models with role-based access
- Factories for all three models
- Tests covering custom behavior: `__str__`, manager methods, and model configuration
- Your first real migration

---

## Why a Custom User Model?

Django ships with a built-in `User` model. It works, but it's locked — you can't add fields to it. If you later need employee IDs, profile photos, or department names, your only option is a separate `Profile` model with a `OneToOneField` back to `User`. That means an extra JOIN on every query and a second table to manage.

A custom user model avoids this entirely. You define your own `User` class, add whatever fields you need, and Django's auth system uses it seamlessly.

**Rule of thumb:** Always create a custom user model before your first migration, even if it's identical to the default. Changing `AUTH_USER_MODEL` after migrations exist is extremely painful — it touches every table that has a foreign key to User.

### `AbstractUser` vs `AbstractBaseUser`

Django provides two base classes:

| Base class | What you get | When to use |
|---|---|---|
| `AbstractUser` | Full auth system: username, email, password, groups, permissions, `is_staff`, `is_active`, `date_joined` | You want Django's auth with custom fields added on top |
| `AbstractBaseUser` | Bare minimum: password and last_login only | You want to completely redesign the user model (rare) |

We use `AbstractUser` because Django's auth machinery (admin login, permission checks, password hashing) is battle-tested and not something we want to rewrite. We just need to add employee-specific fields and swap the login identifier.

---

## Step 1: Write the Tests First

### Factories

Before writing tests, set up factories. Factories generate test data with sensible defaults so your tests stay focused on behavior, not setup.

Create `apps/accounts/tests/factories.py`:

```python
import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Discipline, Membership, Team, User


class DisciplineFactory(DjangoModelFactory):
    class Meta:
        model = Discipline

    name = factory.Sequence(lambda n: f"Discipline {n}")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    employee_id = factory.Sequence(lambda n: 1000 + n)
    email = factory.LazyAttribute(lambda obj: f"{obj.employee_id}@example.com")
    display_name = factory.LazyAttribute(lambda obj: f"User {obj.employee_id}")
    division = ""
    organization = ""
    discipline = None
    is_manager = False


class TeamFactory(DjangoModelFactory):
    class Meta:
        model = Team

    name = factory.Sequence(lambda n: f"Team {n}")
    owner = factory.SubFactory(UserFactory)


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    team = factory.SubFactory(TeamFactory)
    user = factory.SubFactory(UserFactory)
    role = Membership.Role.MEMBER
```

Key factory patterns:

- **`factory.Sequence`** — generates unique values. Each call increments `n`, so you get employee IDs 1000, 1001, 1002...
- **`factory.LazyAttribute`** — derives a value from another field. The email is built from the employee ID, so `UserFactory()` produces consistent data without any arguments.
- **`factory.SubFactory`** — creates a related object automatically. `TeamFactory()` creates both a team and its owner in one call.

### Tests

Create `apps/accounts/tests/test_managers.py` — tests for the custom `UserManager`:

```python
from django.test import TestCase

from apps.accounts.models import User


class TestUserManager(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            employee_id=1001,
            email="jane@example.com",
            password="testpass123",  # noqa: S106
        )
        assert user.pk == 1001
        assert user.employee_id == 1001
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            employee_id=9999,
            email="admin@example.com",
            password="adminpass123",  # noqa: S106
        )
        assert admin.is_staff
        assert admin.is_superuser
```

Create `apps/accounts/tests/test_models.py` — tests for custom model behavior:

```python
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.tests.factories import (
    DisciplineFactory,
    MembershipFactory,
    TeamFactory,
    UserFactory,
)


class TestUser(TestCase):
    def test_employee_id_is_pk(self):
        user = UserFactory(employee_id=42)
        assert user.pk == 42

    def test_username_field(self):
        assert User.USERNAME_FIELD == "employee_id"

    def test_str(self):
        user = UserFactory(employee_id=12345)
        assert str(user) == "12345"


class TestDiscipline(TestCase):
    def test_str(self):
        discipline = DisciplineFactory(name="Design")
        assert str(discipline) == "Design"


class TestTeam(TestCase):
    def test_str(self):
        team = TeamFactory(name="Design")
        assert str(team) == "Design"


class TestMembership(TestCase):
    def test_str(self):
        membership = MembershipFactory()
        expected = (
            f"{membership.user.employee_id} — "
            f"{membership.team.name} ({membership.role})"
        )
        assert str(membership) == expected
```

### What the tests cover — and what they don't

**TestUserManager** — `create_user` and `create_superuser` via the custom manager. These are custom methods we wrote, so they need tests. We verify password hashing works, default flags are correct, and the employee ID is set as the PK.

**TestUser** — employee ID as primary key, `USERNAME_FIELD` configuration, and `__str__`. These test our custom decisions (PK override, login field swap, string representation).

**TestDiscipline / TestTeam / TestMembership** — `__str__` methods only. These are the only custom behavior on these models.

**What we don't test:** uniqueness constraints, ordering, cascade behavior, default field values, timestamps. These are all Django built-in features configured declaratively in `Meta` and field definitions. Django's own test suite covers that `unique=True` enforces uniqueness and `on_delete=CASCADE` cascades deletes. Testing them in our code would just be testing the framework.

**Testing guideline:** Only write model tests for custom methods, properties, and `__str__`. If the behavior comes from a Django field option or `Meta` attribute, trust the framework.

---

## Step 2: Implement the Models

### The custom manager

`AbstractUser` ships with a `UserManager` that expects a `username` parameter. Since we've removed the `username` field, we need our own manager that accepts `employee_id` instead.

Create `apps/accounts/managers.py`:

```python
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, employee_id, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(employee_id=employee_id, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, employee_id, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(employee_id, email, password, **extra_fields)
```

We extend `BaseUserManager` (not `UserManager`) because `UserManager._create_user` hardcodes `self.model(username=username, ...)` — it would crash with our model.

Key points:
- **`set_password()`** — never store raw passwords. This method hashes the password using Django's configured hasher (argon2 in production, MD5 in tests for speed).
- **`self._db`** — supports multi-database setups. Django passes the correct database alias through `using`.
- **`create_superuser` reuses `create_user`** — DRY. The only difference is the defaults for `is_staff` and `is_superuser`.

### Discipline and User models

Create `apps/accounts/models.py`:

```python
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import TimeStampedModel

from .managers import UserManager


class Discipline(TimeStampedModel):
    """HR discipline a user belongs to (e.g., Engineering, Design, Product)."""

    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Custom user model with employee ID as the username and primary key."""

    username = None
    employee_id = models.PositiveIntegerField(unique=True, primary_key=True)
    display_name = models.CharField(max_length=255, blank=True)
    division = models.CharField(max_length=255, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    discipline = models.ForeignKey(
        Discipline,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    is_manager = models.BooleanField(default=False)

    USERNAME_FIELD = "employee_id"
    REQUIRED_FIELDS = ["email"]

    objects = UserManager()

    class Meta:
        ordering = ["employee_id"]

    def __str__(self):
        return str(self.employee_id)
```

There's a lot to unpack here.

### Removing `username` with `username = None`

`AbstractUser` defines `username` as a `CharField`. Since `AbstractUser` is an abstract model, Django allows child classes to override its fields — including removing them entirely by setting them to `None`.

We don't need a string username — our users log in with their employee ID. Setting `username = None` removes the field from the database table completely.

### Employee ID as primary key

```python
employee_id = models.PositiveIntegerField(unique=True, primary_key=True)
```

`primary_key=True` does two things:
1. Makes this field the table's primary key (replaces the auto-generated `id` field)
2. Implies `unique=True` (we include it explicitly for clarity)

Why use the employee ID as the PK? Every employee already has a unique integer ID from the company's HR system. Using it as the PK means:
- No auto-incrementing `id` column to manage
- Foreign keys to User store the employee ID directly — `task.created_by_id` is a meaningful value, not an opaque integer
- Lookups by employee ID are as fast as possible (PK lookups are always indexed)

### `USERNAME_FIELD` and `REQUIRED_FIELDS`

```python
USERNAME_FIELD = "employee_id"
REQUIRED_FIELDS = ["email"]
```

`USERNAME_FIELD` tells Django's auth system which field is the unique login identifier. Admin login, `authenticate()`, and `createsuperuser` all use this field.

`REQUIRED_FIELDS` lists fields that `createsuperuser` prompts for (in addition to `USERNAME_FIELD` and `password`, which are always required). We include `email` so admins get an email address.

### Discipline — the user's HR discipline

In a company's HR hierarchy, users sit within an organization, a division, and a discipline. A discipline is the functional group a person belongs to — Engineering, Design, Product Management, Data Science, etc. It's more specific than division but broader than a project team.

The user profile has three organizational fields: `division`, `organization`, and `discipline`. Division and organization are plain `CharField`s — they're freeform labels from the HR system that we just store and display. A user belongs to exactly one discipline at a time.

Discipline is different from the other two because it's a controlled vocabulary — we want to group and filter users by discipline across the app (e.g., "show all Engineers on this plan", or filter assignees by discipline). Making it a model gives us:
- A canonical list of disciplines (no "Engineering" vs "engineering" vs "Eng" inconsistencies)
- The ability to query: `Discipline.objects.get(name="Engineering").users.all()`
- A FK constraint that prevents orphaned values

Note that `Discipline` is separate from `Team`. A discipline is an HR concept (who you report to), while a team is a Planly concept (who you collaborate with on plans). A user has one discipline but can be a member of many teams.

`SET_NULL` on the FK means: if a discipline is deleted, users in that discipline get `discipline=NULL` rather than being deleted themselves.

### Why User doesn't extend `TimeStampedModel`

`AbstractUser` already provides `date_joined` and `last_login` — these cover the "when was this user created/last active" question. Adding `created_at` and `modified_at` on top would be redundant.

### Team and Membership

```python
class Team(TimeStampedModel):
    """A group of users who collaborate on plans."""

    name = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_teams",
    )
    members = models.ManyToManyField(
        User,
        through="Membership",
        related_name="teams",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    """Explicit M2M through model linking users to teams with roles."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        ordering = ["user__employee_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"],
                name="unique_team_member",
            ),
        ]

    def __str__(self):
        return f"{self.user.employee_id} — {self.team.name} ({self.role})"
```

### `on_delete` strategies

The choice of `on_delete` is one of the most important decisions for each FK:

| Strategy | Behavior | When to use |
|---|---|---|
| `CASCADE` | Deleting the parent deletes all children | Child has no meaning without parent (Membership → Team) |
| `PROTECT` | Prevents deletion of the parent | Deletion would be destructive (Team.owner → User) |
| `SET_NULL` | Sets the FK to NULL | Child survives parent deletion (we'll use this for Task.created_by in Chapter 6) |

`Team.owner` uses `PROTECT` — you can't delete a user who owns a team. Transfer ownership first. `Membership` uses `CASCADE` on both FKs — a membership doesn't make sense without both its team and its user.

### Why an explicit through model?

Django's `ManyToManyField` can create a join table automatically:

```python
members = models.ManyToManyField(User)  # implicit join table
```

But the implicit table only stores two foreign keys — you can't add extra fields like `role` or `joined_at`. By specifying `through="Membership"`, we control the join table and can add whatever fields we need.

### `TextChoices` for roles

```python
class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
```

`TextChoices` creates a string-backed enum. The first value (`"owner"`) is stored in the database; the second (`"Owner"`) is the human-readable label for forms and admin. Using an enum instead of bare strings prevents typos and gives you `Membership.Role.OWNER` for readable code.

### `UniqueConstraint` vs `unique_together`

```python
constraints = [
    models.UniqueConstraint(
        fields=["team", "user"],
        name="unique_team_member",
    ),
]
```

`unique_together` is the old way. `UniqueConstraint` is the modern replacement — it supports conditions (`condition=Q(...)`), deferrable constraints, and explicit naming. Always use `UniqueConstraint` for new code.

The explicit `name` makes database errors readable: instead of a cryptic auto-generated constraint name, you get `unique_team_member` in error messages.

---

## Step 3: Run the Tests (Green)

```bash
uv run pytest apps/accounts/ -v
```

All 34 tests should pass.

---

## Step 4: Create the Migration

This is the first real migration in the project. Until now, our only models were abstract (no tables).

```bash
uv run python manage.py makemigrations accounts
```

```
Migrations for 'accounts':
  apps/accounts/migrations/0001_initial.py
    + Create model Discipline
    + Create model User
    + Create model Membership
    + Create model Team
    + Add field team to membership
    + Create constraint unique_team_member on model membership
```

Apply the migration:

```bash
uv run python manage.py migrate
```

### Why this must happen before any other app's migration

`AUTH_USER_MODEL = "accounts.User"` is set in `base.py`. Every other app that has a FK to User (plans, tasks, notifications) will reference this model. If you try to create those migrations before the accounts migration exists, Django will error.

This is also why changing `AUTH_USER_MODEL` after the first migration is so painful — every existing FK and M2M table would need to be recreated.

---

## Checkpoint

Before moving on, verify:

- [ ] `uv run pytest -v` passes all 46 tests (12 core + 2 settings + 32 accounts)
- [ ] `uv run ruff check apps/ config/` reports no lint errors
- [ ] `uv run python manage.py migrate` completes with no errors
- [ ] `apps/accounts/migrations/0001_initial.py` exists

**Next:** [Chapter 6 — Plans & Tasks: The Core Domain](06-plans-tasks.md)
