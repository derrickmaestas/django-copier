# Testing

## Test Stack

pytest-django with factory_boy. Configuration in `pyproject.toml`:

```toml
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

`--reuse-db` skips database teardown/recreation between runs. `--no-migrations` uses `syncdb` instead — dramatically faster.

## Test Settings

```python
# config/settings/test.py
from config.settings.base import *  # noqa

DEBUG = False
SECRET_KEY = "insecure-test-key-do-not-use-in-production"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # 10x faster
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
TASKS = {"default": {"BACKEND": "django.tasks.backends.dummy.DummyBackend"}}

import tempfile
MEDIA_ROOT = tempfile.mkdtemp()
```

## Factory Boy

Factories live in `apps/<app>/tests/factories.py` alongside test files:

```python
# apps/accounts/tests/factories.py
import factory
from factory.django import DjangoModelFactory
from accounts.models import Membership, Team, User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


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

```python
# apps/plans/tests/factories.py
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

```python
# apps/tasks/tests/factories.py
class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    title = factory.Sequence(lambda n: f"Task {n}")
    bucket = factory.SubFactory(BucketFactory)
    created_by = factory.SubFactory(UserFactory)
    priority = Task.Priority.MEDIUM
    progress = Task.Progress.NOT_STARTED
```

## What to Test at Each Layer

### Model Tests

Only test custom methods, computed properties, and business logic you wrote. Do not test Django's built-in behavior — field declarations, `__str__`, basic CRUD, `auto_now`/`auto_now_add`, constraints enforced by migrations, or ORM defaults all work because Django works.

**Test** — custom methods (`mark_complete()`), properties (`is_overdue`), custom managers/querysets (`for_user()`, `overdue()`), and any non-trivial logic.

**Skip** — `__str__`, field existence, field types, `pk` identity, `USERNAME_FIELD`, `Meta.ordering`, basic save/retrieve, constraint enforcement.

```python
# apps/tasks/tests/test_models.py
import pytest
from django.utils import timezone
from datetime import timedelta

from tasks.tests.factories import TaskFactory
from tasks.models import Task


@pytest.mark.django_db
class TestTaskModel:
    # GOOD — tests custom property logic with edge cases
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

    # GOOD — tests custom method with side effects
    def test_mark_complete_sets_progress_and_timestamp(self):
        task = TaskFactory()
        task.mark_complete()
        task.refresh_from_db()
        assert task.progress == Task.Progress.COMPLETED
        assert task.completed_at is not None
```

```python
# BAD — tests Django, not your code. Don't write these.
class TestTaskModel:
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

### View Tests

Test HTTP status, redirects, context, and permissions:

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

### Background Task Tests

Use `DummyBackend` to assert tasks were enqueued without executing them:

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

### API Tests (DRF)

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
        self.client.force_authenticate(user=self.user)

    def test_create_task(self):
        bucket = BucketFactory(plan=self.membership.team.plans.first())
        response = self.client.post("/api/v1/tasks/", {
            "title": "New task",
            "bucket": bucket.pk,
            "priority": 5,
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New task"

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

## Coverage

85% is the practical floor. Focus coverage on custom methods, business logic, and permission checks. Don't write tests for Django's own behavior (`__str__`, field declarations, `auto_now`, constraints). Admin configuration and boilerplate `apps.py` don't need tests either.

```bash
pytest --cov=apps/ --cov-report=term-missing
```
