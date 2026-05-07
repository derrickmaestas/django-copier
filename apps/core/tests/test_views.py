from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.urls import reverse

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.tests.factories import CommentFactory, TaskFactory


@pytest.mark.django_db
class TestHealthEndpoint:
    """`/health/` is a public liveness + readiness probe."""

    def test_returns_200_when_db_is_reachable(self, client):
        response = client.get(reverse("core:health"))
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_no_login_required(self, client):
        """LB/orchestrator probes hit this endpoint without credentials."""
        response = client.get(reverse("core:health"))
        assert response.status_code == 200

    def test_returns_503_when_db_is_down(self, client):
        """Simulate a connection failure and assert the right status."""
        with patch(
            "apps.core.views.connection.ensure_connection",
            side_effect=DatabaseError("fake outage"),
        ):
            response = client.get(reverse("core:health"))
        assert response.status_code == 503
        assert response.json() == {"status": "db_unreachable"}

    def test_only_get_allowed(self, client):
        response = client.post(reverse("core:health"))
        assert response.status_code == 405


@pytest.fixture
def member_team(client):
    user = UserFactory()
    user.set_password("pw")
    user.save()
    team = TeamFactory()
    MembershipFactory(team=team, user=user)
    client.force_login(user)
    return client, user, team


@pytest.mark.django_db
class TestSearchView:
    """GET /search/ runs FTS and returns mixed Plan + Task results."""

    def test_empty_query_renders_prompt(self, member_team):
        client, _, _ = member_team

        response = client.get(reverse("core:search"))

        assert response.status_code == 200
        assert b"Type a query to begin" in response.content

    def test_finds_plan_by_title(self, member_team):
        client, user, team = member_team
        PlanFactory(team=team, title="Q3 Roadmap")

        response = client.get(reverse("core:search"), {"q": "roadmap"})

        assert response.status_code == 200
        assert b"Q3 Roadmap" in response.content

    def test_finds_task_via_comment(self, member_team):
        """A task whose own text doesn't match the query but whose comment does."""
        client, user, team = member_team
        bucket = BucketFactory(plan=PlanFactory(team=team))
        task = TaskFactory(bucket=bucket, title="Investigate latency")
        CommentFactory(task=task, body="It's the kanban query.")

        response = client.get(reverse("core:search"), {"q": "kanban"})

        assert b"Investigate latency" in response.content

    def test_type_filter_excludes_other_resources(self, member_team):
        """`?type=task` skips the Plans section regardless of plan matches."""
        client, user, team = member_team
        # Use distinct non-overlapping titles so the assertions can't be
        # confused by the parent-plan label rendered next to a task hit.
        PlanFactory(team=team, title="Onboarding manual")
        bucket = BucketFactory(plan=PlanFactory(team=team, title="Quarterly planning"))
        TaskFactory(bucket=bucket, title="Onboarding audit")

        response = client.get(
            reverse("core:search"), {"q": "onboarding", "type": "task"}
        )

        assert b"Onboarding audit" in response.content
        # The plan whose title also matches "onboarding" must not appear.
        assert b"Onboarding manual" not in response.content

    def test_does_not_leak_other_team_results(self, member_team):
        client, _, _ = member_team
        # Plan on a team the user isn't a member of
        PlanFactory(team=TeamFactory(), title="Secret Project Phoenix")

        response = client.get(reverse("core:search"), {"q": "phoenix"})

        assert b"Secret Project Phoenix" not in response.content

    def test_htmx_request_returns_partial(self, member_team):
        client, user, team = member_team
        PlanFactory(team=team, title="Q3 Roadmap")

        response = client.get(
            reverse("core:search"),
            {"q": "roadmap"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        # Partial response — no <html> shell
        assert b"<html" not in response.content
        assert b"Q3 Roadmap" in response.content

    def test_unauth_redirects_to_login(self, client):
        response = client.get(reverse("core:search"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url
