from datetime import timedelta

import pytest
from django.utils import timezone

from apps.tasks.models import Task
from apps.tasks.tests.factories import AssignmentFactory, ChecklistItemFactory, TaskFactory


@pytest.mark.django_db
class TestTaskQuerySetAssignedTo:
    """TaskQuerySet.assigned_to() returns tasks the user is explicitly assigned to."""

    def test_returns_assigned_tasks(self):
        assignment = AssignmentFactory()

        result = Task.objects.assigned_to(assignment.user)

        assert assignment.task in result

    def test_excludes_unassigned_tasks(self):
        assignment = AssignmentFactory()
        other_task = TaskFactory()

        result = Task.objects.assigned_to(assignment.user)

        assert other_task not in result

    def test_no_duplicates_with_multiple_assignments(self):
        """A task with multiple assignees shouldn't appear multiple times for one user."""
        assignment = AssignmentFactory()
        # Add a second assignee to the same task
        AssignmentFactory(task=assignment.task)

        result = Task.objects.assigned_to(assignment.user)

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
