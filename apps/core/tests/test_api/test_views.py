import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.tests.factories import CommentFactory, TaskFactory


@pytest.fixture
def member_client():
    user = UserFactory()
    team = TeamFactory()
    MembershipFactory(team=team, user=user)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, team


@pytest.mark.django_db
class TestSearchAPIEmptyQuery:
    """GET /api/v1/search/ without a query returns an empty list, not an error."""

    def test_no_query_returns_empty(self, member_client):
        client, _, _ = member_client

        response = client.get("/api/v1/search/")

        assert response.status_code == 200
        assert response.data == []


@pytest.mark.django_db
class TestSearchAPIMixedResults:
    """Hits include both plans and tasks merged by rank with type discriminator."""

    def test_returns_plan_and_task_hits(self, member_client):
        client, user, team = member_client
        PlanFactory(team=team, title="Migration Roadmap")
        bucket = BucketFactory(plan=PlanFactory(team=team))
        TaskFactory(bucket=bucket, title="Migration audit")

        response = client.get("/api/v1/search/?q=migration")

        types = {hit["type"] for hit in response.data}
        assert types == {"plan", "task"}

    def test_each_hit_has_required_fields(self, member_client):
        client, user, team = member_client
        PlanFactory(team=team, title="Q3 Roadmap")

        response = client.get("/api/v1/search/?q=roadmap")

        hit = response.data[0]
        assert hit["type"] == "plan"
        assert "id" in hit
        assert hit["title"] == "Q3 Roadmap"
        assert hit["url"].startswith("/plans/")
        assert isinstance(hit["rank"], float)
        assert "headline" in hit


@pytest.mark.django_db
class TestSearchAPITypeFilter:
    """`?type=plan` and `?type=task` narrow to a single resource kind."""

    def test_type_plan_excludes_tasks(self, member_client):
        client, user, team = member_client
        PlanFactory(team=team, title="Authentication revamp")
        TaskFactory(
            bucket=BucketFactory(plan=PlanFactory(team=team)),
            title="Authentication audit",
        )

        response = client.get(
            "/api/v1/search/?q=authentication&type=plan"
        )

        types = {hit["type"] for hit in response.data}
        assert types == {"plan"}

    def test_type_task_excludes_plans(self, member_client):
        client, user, team = member_client
        PlanFactory(team=team, title="Authentication revamp")
        TaskFactory(
            bucket=BucketFactory(plan=PlanFactory(team=team)),
            title="Authentication audit",
        )

        response = client.get(
            "/api/v1/search/?q=authentication&type=task"
        )

        types = {hit["type"] for hit in response.data}
        assert types == {"task"}


@pytest.mark.django_db
class TestSearchAPITeamScoping:
    """Non-team-member resources never appear in results."""

    def test_does_not_leak_other_team_plans(self, member_client):
        client, _, _ = member_client
        PlanFactory(team=TeamFactory(), title="Secret Phoenix")

        response = client.get("/api/v1/search/?q=phoenix")

        assert response.data == []


@pytest.mark.django_db
class TestPlanListSearchUsesFTS:
    """`?search=` on /api/v1/plans/ now hits FTS, including the comment-fan-out path on tasks."""

    def test_plan_list_search_matches_description(self, member_client):
        client, user, team = member_client
        PlanFactory(team=team, title="Hiring", description="quarterly cadence review")
        PlanFactory(team=team, title="Operations", description="weekly standup")

        response = client.get("/api/v1/plans/?search=cadence")

        titles = [row["title"] for row in response.data["results"]]
        assert titles == ["Hiring"]


@pytest.mark.django_db
class TestTaskListSearchUsesFTS:
    """`?search=` on /api/v1/tasks/ matches comment text, not just title/description."""

    def test_task_list_search_matches_comment(self, member_client):
        client, user, team = member_client
        bucket = BucketFactory(plan=PlanFactory(team=team))
        task = TaskFactory(bucket=bucket, title="Investigate latency")
        CommentFactory(task=task, body="kanban query plan looks suspicious")

        response = client.get("/api/v1/tasks/?search=kanban")

        ids = [row["id"] for row in response.data["results"]]
        assert task.pk in ids

    def test_unauth_returns_401(self):
        response = APIClient().get("/api/v1/search/?q=anything")
        assert response.status_code == 401
