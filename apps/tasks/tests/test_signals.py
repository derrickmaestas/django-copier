import pytest

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification
from apps.tasks.models import Task
from apps.tasks.tests.factories import (
    AssignmentFactory,
    CommentFactory,
    TaskFactory,
)


@pytest.fixture
def immediate_tasks(settings):
    """Run enqueued django.tasks inline so we can assert on their effects."""
    settings.TASKS = {
        "default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"},
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("immediate_tasks")
class TestCommentSignal:
    """Posting a comment fans a notification out to the task's watchers."""

    def test_notifies_assignees_and_creator(self):
        creator = UserFactory()
        assignee_a = UserFactory()
        assignee_b = UserFactory()
        task = TaskFactory(created_by=creator)
        AssignmentFactory(task=task, user=assignee_a)
        AssignmentFactory(task=task, user=assignee_b)

        commenter = UserFactory()
        CommentFactory(task=task, created_by=commenter)

        recipients = set(
            Notification.objects.values_list("recipient_id", flat=True)
        )
        assert recipients == {creator.pk, assignee_a.pk, assignee_b.pk}

    def test_skips_self_when_commenter_is_assignee(self):
        creator = UserFactory()
        commenter = UserFactory()
        task = TaskFactory(created_by=creator)
        AssignmentFactory(task=task, user=commenter)

        CommentFactory(task=task, created_by=commenter)

        recipients = set(
            Notification.objects.values_list("recipient_id", flat=True)
        )
        assert recipients == {creator.pk}

    def test_no_notifications_when_only_watcher_is_commenter(self):
        commenter = UserFactory()
        task = TaskFactory(created_by=commenter)

        CommentFactory(task=task, created_by=commenter)

        assert Notification.objects.count() == 0

    def test_only_fires_on_create(self):
        comment = CommentFactory()
        Notification.objects.all().delete()

        comment.body = "edited"
        comment.save()

        assert Notification.objects.count() == 0


@pytest.mark.django_db
class TestTaskCompletedAtInvariant:
    """A pre_save signal stamps completed_at when progress hits 100%."""

    def test_direct_save_to_complete_stamps_completed_at(self):
        task = TaskFactory(progress=Task.Progress.NOT_STARTED)

        task.progress = Task.Progress.COMPLETED
        task.save()
        task.refresh_from_db()

        assert task.completed_at is not None

    def test_progress_below_100_does_not_stamp(self):
        task = TaskFactory(progress=Task.Progress.NOT_STARTED)

        task.progress = Task.Progress.IN_PROGRESS
        task.save()
        task.refresh_from_db()

        assert task.completed_at is None

    def test_repeated_save_at_100_keeps_original_timestamp(self):
        task = TaskFactory(progress=Task.Progress.NOT_STARTED)
        task.progress = Task.Progress.COMPLETED
        task.save()
        task.refresh_from_db()
        first_stamp = task.completed_at

        task.description = "edited"
        task.save()
        task.refresh_from_db()

        assert task.completed_at == first_stamp

    def test_create_at_100_stamps_completed_at(self):
        task = TaskFactory(progress=Task.Progress.COMPLETED)

        assert task.completed_at is not None
