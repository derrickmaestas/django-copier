import pytest

from apps.notifications.tests.factories import (
    NotificationFactory,
    NotificationPreferenceFactory,
)


@pytest.mark.django_db
class TestNotificationStr:
    def test_str(self):
        notification = NotificationFactory(verb="assigned")
        expected = f"{notification.actor} assigned → {notification.recipient}"
        assert str(notification) == expected


@pytest.mark.django_db
class TestNotificationIsRead:
    def test_unread_by_default(self):
        notification = NotificationFactory()
        assert notification.is_read is False

    def test_read_when_read_at_set(self):
        notification = NotificationFactory()
        notification.mark_read()
        assert notification.is_read is True


@pytest.mark.django_db
class TestNotificationMarkRead:
    def test_sets_read_at_timestamp(self):
        notification = NotificationFactory()
        assert notification.read_at is None

        notification.mark_read()
        notification.refresh_from_db()

        assert notification.read_at is not None

    def test_idempotent(self):
        """Calling mark_read twice should not overwrite the original timestamp."""
        notification = NotificationFactory()
        notification.mark_read()
        first_timestamp = notification.read_at

        notification.mark_read()
        notification.refresh_from_db()

        assert notification.read_at == first_timestamp


@pytest.mark.django_db
class TestNotificationPreferenceStr:
    def test_str(self):
        pref = NotificationPreferenceFactory()
        assert str(pref) == f"Preferences for {pref.user}"
