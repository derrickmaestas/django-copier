import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory


@pytest.fixture
def authed():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
class TestNotificationList:
    """GET /api/v1/notifications/ returns only the current user's notifications."""

    def test_only_own_notifications(self, authed):
        client, user = authed
        own = NotificationFactory(recipient=user)
        NotificationFactory(recipient=UserFactory())

        response = client.get("/api/v1/notifications/")

        assert response.status_code == 200
        ids = {row["id"] for row in response.data["results"]}
        assert ids == {own.pk}


@pytest.mark.django_db
class TestNotificationIsReadOnly:
    """Direct write methods are not exposed on the notification ViewSet."""

    def test_post_returns_405(self, authed):
        client, _ = authed
        response = client.post(
            "/api/v1/notifications/", {"verb": "assigned"}, format="json"
        )
        assert response.status_code == 405

    def test_delete_returns_405(self, authed):
        client, user = authed
        notif = NotificationFactory(recipient=user)
        response = client.delete(f"/api/v1/notifications/{notif.pk}/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestMarkRead:
    """POST /api/v1/notifications/{id}/mark_read/ stamps read_at."""

    def test_marks_unread_notification_read(self, authed):
        client, user = authed
        notif = NotificationFactory(recipient=user)
        assert notif.read_at is None

        response = client.post(f"/api/v1/notifications/{notif.pk}/mark_read/")

        assert response.status_code == 200
        notif.refresh_from_db()
        assert notif.read_at is not None
        assert response.data["is_read"] is True

    def test_cannot_mark_other_users_notification(self, authed):
        client, _ = authed
        other_notif = NotificationFactory(recipient=UserFactory())

        response = client.post(
            f"/api/v1/notifications/{other_notif.pk}/mark_read/"
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestMarkAllRead:
    """POST /api/v1/notifications/mark_all_read/ bulk-marks unread ones."""

    def test_bulk_mark_all_read(self, authed):
        client, user = authed
        NotificationFactory(recipient=user)
        NotificationFactory(recipient=user)
        other = NotificationFactory(recipient=UserFactory())

        response = client.post("/api/v1/notifications/mark_all_read/")

        assert response.status_code == 200
        assert response.data["updated"] == 2
        assert (
            Notification.objects.filter(recipient=user, read_at__isnull=True).count()
            == 0
        )
        other.refresh_from_db()
        assert other.read_at is None
