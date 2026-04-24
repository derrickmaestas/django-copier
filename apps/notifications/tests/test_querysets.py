import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory


@pytest.mark.django_db
class TestNotificationQuerySetForUser:
    def test_returns_recipients_notifications(self):
        user = UserFactory()
        notification = NotificationFactory(recipient=user)

        result = Notification.objects.for_user(user)

        assert notification in result

    def test_excludes_other_users_notifications(self):
        NotificationFactory()
        other_user = UserFactory()

        result = Notification.objects.for_user(other_user)

        assert result.count() == 0


@pytest.mark.django_db
class TestNotificationQuerySetUnread:
    def test_returns_notifications_without_read_at(self):
        notification = NotificationFactory()

        assert notification in Notification.objects.unread()

    def test_excludes_read_notifications(self):
        notification = NotificationFactory(read_at=timezone.now())

        assert notification not in Notification.objects.unread()


@pytest.mark.django_db
class TestNotificationQuerySetMarkAllRead:
    def test_sets_read_at_on_all_unread(self):
        user = UserFactory()
        NotificationFactory(recipient=user)
        NotificationFactory(recipient=user)

        Notification.objects.for_user(user).mark_all_read()

        assert Notification.objects.for_user(user).unread().count() == 0

    def test_does_not_overwrite_existing_read_at(self):
        """Already-read notifications keep their original read_at timestamp."""
        user = UserFactory()
        original = timezone.now()
        read_notification = NotificationFactory(recipient=user, read_at=original)

        Notification.objects.for_user(user).mark_all_read()

        read_notification.refresh_from_db()
        assert read_notification.read_at == original
