import pytest

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification
from apps.notifications.tasks import send_assignment_notification
from apps.tasks.tests.factories import TaskFactory


@pytest.fixture
def immediate_tasks(settings):
    """Run enqueued django.tasks inline so we can assert on their effects."""
    settings.TASKS = {
        "default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"},
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("immediate_tasks")
class TestSendAssignmentNotification:
    """The django.tasks function that creates Notification rows on assign."""

    def test_creates_notification_for_assignee(self):
        actor = UserFactory()
        assignee = UserFactory()
        task = TaskFactory()

        send_assignment_notification.enqueue(task.pk, assignee.pk, actor.pk)

        notif = Notification.objects.get()
        assert notif.recipient_id == assignee.pk
        assert notif.actor_id == actor.pk
        assert notif.verb == Notification.Verb.ASSIGNED
        assert notif.target == task
        assert task.title in notif.description

    def test_skips_when_actor_assigns_themselves(self):
        user = UserFactory()
        task = TaskFactory()

        send_assignment_notification.enqueue(task.pk, user.pk, user.pk)

        assert Notification.objects.count() == 0

    def test_no_actor_still_creates_notification(self):
        assignee = UserFactory()
        task = TaskFactory()

        send_assignment_notification.enqueue(task.pk, assignee.pk)

        notif = Notification.objects.get()
        assert notif.recipient_id == assignee.pk
        assert notif.actor_id is None

    def test_unknown_task_is_silent(self):
        assignee = UserFactory()

        send_assignment_notification.enqueue(999_999, assignee.pk, None)

        assert Notification.objects.count() == 0
