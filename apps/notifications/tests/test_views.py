import datetime

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.notifications.tests.factories import NotificationFactory


@pytest.mark.django_db
class TestNotificationListView:
    def test_only_recipient_sees_their_notifications(self, client):
        user = UserFactory()
        mine = NotificationFactory(recipient=user)
        NotificationFactory()  # someone else's

        client.force_login(user)
        response = client.get(reverse("notifications:notification-list"))

        assert list(response.context["notifications"]) == [mine]

    def test_redirects_anonymous_to_login(self, client):
        response = client.get(reverse("notifications:notification-list"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url


@pytest.mark.django_db
class TestNotificationMarkRead:
    def test_recipient_can_mark_read(self, client):
        user = UserFactory()
        notif = NotificationFactory(recipient=user)
        client.force_login(user)

        response = client.post(
            reverse("notifications:notification-mark-read", kwargs={"pk": notif.pk}),
        )

        notif.refresh_from_db()
        assert notif.read_at is not None
        assert response.status_code == 302

    def test_non_recipient_gets_404(self, client):
        user = UserFactory()
        notif = NotificationFactory()  # someone else's
        client.force_login(user)

        response = client.post(
            reverse("notifications:notification-mark-read", kwargs={"pk": notif.pk}),
        )

        assert response.status_code == 404
        notif.refresh_from_db()
        assert notif.read_at is None


@pytest.mark.django_db
class TestNotificationMarkAllRead:
    def test_marks_only_recipients_unread(self, client):
        user = UserFactory()
        mine_unread = NotificationFactory(recipient=user)
        already_read_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
        mine_read = NotificationFactory(recipient=user, read_at=already_read_at)
        someone_elses = NotificationFactory()

        client.force_login(user)
        client.post(reverse("notifications:notification-mark-all-read"))

        mine_unread.refresh_from_db()
        mine_read.refresh_from_db()
        someone_elses.refresh_from_db()
        assert mine_unread.read_at is not None
        assert mine_read.read_at == already_read_at  # unchanged
        assert someone_elses.read_at is None  # untouched
