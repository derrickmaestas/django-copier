"""Hard caps on the query count of the notifications hot paths."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.notifications.tests.factories import NotificationFactory


@pytest.mark.django_db
class TestNotificationListViewQueryCount:
    """`/notifications/` paginates 25 rows of mixed-actor notifications."""

    def test_constant_query_count_when_dataset_grows(
        self, client, django_assert_num_queries
    ):
        """select_related("actor") keeps actor lookups out of the per-row loop."""
        user = UserFactory()
        user.set_password("pw")
        user.save()
        # 30 notifications from many distinct actors — paginated to 25 per page.
        for _ in range(30):
            NotificationFactory(recipient=user)

        client.force_login(user)
        # Four queries: session, current user, the COUNT for pagination,
        # the SELECT (with actor JOIN via select_related). The list runs
        # at constant cost regardless of actor diversity because actors
        # are reached via JOIN, not a per-row lookup.
        with django_assert_num_queries(4):
            response = client.get("/notifications/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestNotificationAPIQueryCount:
    """`/api/v1/notifications/` is the JSON equivalent."""

    def test_constant_query_count(self, django_assert_num_queries):
        user = UserFactory()
        for _ in range(30):
            NotificationFactory(recipient=user)
        client = APIClient()
        client.force_authenticate(user=user)

        # Two queries: pagination COUNT, the SELECT (with actor and
        # target_content_type JOINs via select_related). force_authenticate
        # bypasses session/user lookups.
        with django_assert_num_queries(2):
            response = client.get("/api/v1/notifications/")
        assert response.status_code == 200
