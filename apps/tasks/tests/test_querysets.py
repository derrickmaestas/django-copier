from datetime import timedelta

import pytest
from django.utils import timezone

from apps.tasks.models import Task
from apps.tasks.tests.factories import (
    AssignmentFactory,
    ChecklistItemFactory,
    CommentFactory,
    TaskFactory,
)


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
    """TaskQuerySet.search() runs Postgres FTS against the trigger-maintained vector."""

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

    def test_matches_comment_body_via_trigger(self):
        """Tier 2: a task is found because of one of its comments, not its own text."""
        task = TaskFactory(title="Investigate latency", description="profile dashboard")
        CommentFactory(task=task, body="Pretty sure it's the kanban query plan.")

        result = Task.objects.search("kanban")

        assert task in result

    def test_comment_edit_updates_search_vector(self):
        """Editing a comment body re-fires the fan-out trigger."""
        task = TaskFactory(title="Latency", description="")
        comment = CommentFactory(task=task, body="kanban query")

        comment.body = "graphql resolver"
        comment.save()

        assert task not in Task.objects.search("kanban")
        assert task in Task.objects.search("graphql")

    def test_comment_delete_updates_search_vector(self):
        """Deleting a comment removes its lexemes from the parent task's vector."""
        task = TaskFactory(title="Latency", description="")
        comment = CommentFactory(task=task, body="bottleneck spotted")

        comment.delete()

        assert task not in Task.objects.search("bottleneck")

    def test_unaccent_matches_diacritics(self):
        task = TaskFactory(title="Café outage", description="")

        result = Task.objects.search("cafe")

        assert task in result

    def test_empty_query_returns_empty(self):
        TaskFactory()
        assert list(Task.objects.search("")) == []

    def test_with_headline_annotates_snippet(self):
        TaskFactory(description="we ship the dashboard rewrite by Friday")

        task = Task.objects.search("dashboard", with_headline=True).first()

        assert task is not None
        assert "<b>" in task.headline
