from datetime import timedelta

import pytest
from django.utils import timezone

from apps.tasks.models import Task
from apps.tasks.tests.factories import TaskFactory


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
